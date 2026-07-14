import { useCallback, useEffect, useRef, useState } from 'react';
import { voiceSocketUrl } from '../api';

/**
 * useVoiceSession — a self-contained real-time voice client for one conversation.
 *
 * Owns the whole audio duplex: mic capture (16kHz mono Int16 PCM via an AudioWorklet),
 * a WebSocket to the backend voice proxy, and playback of the model's 24kHz PCM with
 * barge-in support. Exposes a tiny declarative surface the UI renders from:
 *
 *   status        'idle' | 'connecting' | 'live' | 'error'
 *   error         string | null
 *   speaking      true while the model's audio is playing (drives the avatar animation)
 *   listening     true while connected and the model is NOT speaking (i.e. mic is hot)
 *   inputText     rolling transcript of what the USER is saying this turn
 *   outputText    rolling transcript of what the PERSONA is saying this turn
 *   scores        array of live word-score pops {id, word, event_type, delta, score_after, note}
 *   start()       request mic, connect, begin streaming
 *   stop()        graceful end (tells the server to persist, tears everything down)
 *
 * Everything is ref-based so re-renders never restart audio. Designed to be dropped into
 * any screen — it knows nothing about the overlay UI.
 */

const MIC_SAMPLE_RATE = 16000;
const PLAYBACK_SAMPLE_RATE = 24000;

// The AudioWorklet processor: downstream from the mic, converts Float32 frames to Int16 PCM
// and ships each block to the main thread. Inlined as a blob so there's no public asset.
const WORKLET_SRC = `
class PcmProcessor extends AudioWorkletProcessor {
  process(inputs) {
    const input = inputs[0];
    if (input && input.length > 0) {
      const samples = input[0];
      const pcm16 = new Int16Array(samples.length);
      for (let i = 0; i < samples.length; i++) {
        const s = Math.max(-1, Math.min(1, samples[i]));
        pcm16[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
      }
      this.port.postMessage(pcm16.buffer, [pcm16.buffer]);
    }
    return true;
  }
}
registerProcessor('pcm-processor', PcmProcessor);
`;

function base64FromBytes(bytes) {
  let binary = '';
  const chunk = 0x8000;
  for (let i = 0; i < bytes.length; i += chunk) {
    binary += String.fromCharCode.apply(null, bytes.subarray(i, i + chunk));
  }
  return btoa(binary);
}

export function useVoiceSession(conversationId) {
  const [status, setStatus] = useState('idle');
  const [error, setError] = useState(null);
  const [speaking, setSpeaking] = useState(false);
  const [inputText, setInputText] = useState('');
  const [outputText, setOutputText] = useState('');
  const [scores, setScores] = useState([]);

  // --- refs (never trigger re-render) ---
  const wsRef = useRef(null);
  const micCtxRef = useRef(null);
  const playCtxRef = useRef(null);
  const streamRef = useRef(null);
  const workletRef = useRef(null);
  const sourceRef = useRef(null);
  const playQueueRef = useRef([]);
  const playingRef = useRef(false);
  const playHeadRef = useRef(0); // scheduled-until time in the playback context
  const activeSourcesRef = useRef([]); // currently-scheduled buffer sources (for barge-in)
  const scoreSeqRef = useRef(0);
  const stoppedRef = useRef(false);

  // ---- Playback ----
  const clearPlayback = useCallback(() => {
    playQueueRef.current = [];
    playingRef.current = false;
    playHeadRef.current = 0;
    activeSourcesRef.current.forEach((s) => {
      try { s.onended = null; s.stop(); } catch { /* already stopped */ }
    });
    activeSourcesRef.current = [];
    setSpeaking(false);
  }, []);

  const pumpPlayback = useCallback(() => {
    const ctx = playCtxRef.current;
    if (!ctx) return;
    // Schedule everything queued, back-to-back, gapless.
    while (playQueueRef.current.length > 0) {
      const bytes = playQueueRef.current.shift();
      const samples = new Int16Array(bytes.buffer, bytes.byteOffset, bytes.byteLength / 2);
      const floats = new Float32Array(samples.length);
      for (let i = 0; i < samples.length; i++) floats[i] = samples[i] / 32768;

      const buffer = ctx.createBuffer(1, floats.length, PLAYBACK_SAMPLE_RATE);
      buffer.getChannelData(0).set(floats);
      const src = ctx.createBufferSource();
      src.buffer = buffer;
      src.connect(ctx.destination);

      const startAt = Math.max(ctx.currentTime, playHeadRef.current);
      src.start(startAt);
      playHeadRef.current = startAt + buffer.duration;
      activeSourcesRef.current.push(src);
      setSpeaking(true);

      src.onended = () => {
        activeSourcesRef.current = activeSourcesRef.current.filter((s) => s !== src);
        if (activeSourcesRef.current.length === 0 && playQueueRef.current.length === 0) {
          setSpeaking(false);
        }
      };
    }
  }, []);

  const enqueueAudio = useCallback((b64) => {
    const binary = atob(b64);
    const bytes = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
    playQueueRef.current.push(bytes);
    pumpPlayback();
  }, [pumpPlayback]);

  // ---- Teardown ----
  const teardown = useCallback(() => {
    try { workletRef.current?.disconnect(); } catch { /* noop */ }
    try { sourceRef.current?.disconnect(); } catch { /* noop */ }
    try { streamRef.current?.getTracks().forEach((t) => t.stop()); } catch { /* noop */ }
    try { micCtxRef.current?.close(); } catch { /* noop */ }
    try { playCtxRef.current?.close(); } catch { /* noop */ }
    workletRef.current = null;
    sourceRef.current = null;
    streamRef.current = null;
    micCtxRef.current = null;
    playCtxRef.current = null;
    if (wsRef.current) {
      try { wsRef.current.close(); } catch { /* noop */ }
      wsRef.current = null;
    }
    clearPlayback();
  }, [clearPlayback]);

  const stop = useCallback(() => {
    stoppedRef.current = true;
    // Ask the server to flush/persist the final turn before we drop the socket.
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      try { wsRef.current.send(JSON.stringify({ type: 'end' })); } catch { /* noop */ }
    }
    teardown();
    setStatus('idle');
    setSpeaking(false);
  }, [teardown]);

  // ---- Start ----
  const start = useCallback(async () => {
    if (status === 'connecting' || status === 'live') return;
    stoppedRef.current = false;
    setError(null);
    setInputText('');
    setOutputText('');
    setScores([]);
    setStatus('connecting');

    try {
      // Playback context (24kHz output from the model).
      playCtxRef.current = new (window.AudioContext || window.webkitAudioContext)();

      // Mic context at 16kHz.
      const micCtx = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: MIC_SAMPLE_RATE });
      micCtxRef.current = micCtx;

      const stream = await navigator.mediaDevices.getUserMedia({
        audio: { sampleRate: MIC_SAMPLE_RATE, channelCount: 1, echoCancellation: true, noiseSuppression: true },
      });
      streamRef.current = stream;

      const blobUrl = URL.createObjectURL(new Blob([WORKLET_SRC], { type: 'text/javascript' }));
      await micCtx.audioWorklet.addModule(blobUrl);
      URL.revokeObjectURL(blobUrl);

      const source = micCtx.createMediaStreamSource(stream);
      const worklet = new AudioWorkletNode(micCtx, 'pcm-processor');
      source.connect(worklet);
      // NOTE: intentionally NOT connecting worklet -> destination (no mic monitoring/echo).
      sourceRef.current = source;
      workletRef.current = worklet;

      // Open the socket.
      const ws = new WebSocket(voiceSocketUrl(conversationId));
      wsRef.current = ws;

      worklet.port.onmessage = (event) => {
        if (ws.readyState !== WebSocket.OPEN) return;
        const bytes = new Uint8Array(event.data);
        ws.send(JSON.stringify({ type: 'audio', data: base64FromBytes(bytes) }));
      };

      ws.onmessage = (event) => {
        let msg;
        try { msg = JSON.parse(event.data); } catch { return; }
        switch (msg.type) {
          case 'ready':
            setStatus('live');
            break;
          case 'audio':
            enqueueAudio(msg.data);
            break;
          case 'input_transcript':
            setInputText((t) => t + msg.text);
            break;
          case 'output_transcript':
            setOutputText((t) => t + msg.text);
            break;
          case 'score':
            scoreSeqRef.current += 1;
            setScores((prev) => [
              ...prev,
              {
                id: scoreSeqRef.current,
                word: msg.word,
                event_type: msg.event_type,
                delta: msg.delta,
                score_after: msg.score_after,
                note: msg.note,
              },
            ]);
            break;
          case 'interrupted':
            clearPlayback();
            break;
          case 'turn_complete':
            // New turn begins: reset the rolling transcripts for the next exchange.
            setInputText('');
            setOutputText('');
            break;
          case 'error':
            setError(msg.message || 'Voice error');
            setStatus('error');
            break;
          default:
            break;
        }
      };

      ws.onerror = () => {
        if (!stoppedRef.current) { setError('Connection lost'); setStatus('error'); }
      };
      ws.onclose = () => {
        // A close we didn't initiate (network drop, server error) — surface it rather than
        // silently reverting to the pre-start "idle" look, which reads as being stuck.
        if (!stoppedRef.current) {
          setError((e) => e || 'Connection ended');
          setStatus((s) => (s === 'error' ? s : 'error'));
        }
      };
    } catch (e) {
      setError(e?.message || 'Could not start the microphone');
      setStatus('error');
      teardown();
    }
  }, [conversationId, status, enqueueAudio, clearPlayback, teardown]);

  // Cleanup on unmount.
  useEffect(() => () => teardown(), [teardown]);

  // Remove a score pop after its animation (kept short so pops don't pile up).
  const dismissScore = useCallback((id) => {
    setScores((prev) => prev.filter((s) => s.id !== id));
  }, []);

  const listening = status === 'live' && !speaking;

  return { status, error, speaking, listening, inputText, outputText, scores, dismissScore, start, stop };
}

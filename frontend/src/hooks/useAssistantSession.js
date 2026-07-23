import { useCallback, useEffect, useRef, useState } from 'react';
import { assistantSocketUrl } from '../api';

/**
 * useAssistantSession — the real-time voice client for the Fluently in-app assistant.
 *
 * A trimmed sibling of useVoiceSession: same audio duplex (16kHz mic in via an AudioWorklet,
 * 24kHz PCM playback with barge-in), but talks to /api/assistant/ws (ephemeral — nothing saved,
 * nothing scored) instead of a persona conversation, and surfaces `actions` (a tool did
 * something) instead of `scores`.
 *
 *   status      'idle' | 'connecting' | 'live' | 'error'
 *   speaking    model audio is playing (drives the avatar animation)
 *   listening   connected and not speaking (mic hot)
 *   inputText   rolling transcript of what the USER is saying this turn
 *   outputText  rolling transcript of what FLUENTLY is saying this turn
 *   actions     [{id, name, message}] — confirmations of things the assistant just did
 *   start()/stop()/dismissAction(id)
 *
 * `tab` is the app screen the user is on (chat/words/memory/settings) — passed to the backend so
 * the assistant can ground its help. Everything is ref-based so re-renders never restart audio.
 */

const MIC_SAMPLE_RATE = 16000;
const PLAYBACK_SAMPLE_RATE = 24000;

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

export function useAssistantSession(tab) {
  const [status, setStatus] = useState('idle');
  const [error, setError] = useState(null);
  const [speaking, setSpeaking] = useState(false);
  const [inputText, setInputText] = useState('');
  const [outputText, setOutputText] = useState('');
  const [actions, setActions] = useState([]);

  const wsRef = useRef(null);
  const micCtxRef = useRef(null);
  const playCtxRef = useRef(null);
  const streamRef = useRef(null);
  const workletRef = useRef(null);
  const sourceRef = useRef(null);
  const playQueueRef = useRef([]);
  const playHeadRef = useRef(0);
  const activeSourcesRef = useRef([]);
  const actionSeqRef = useRef(0);
  const stoppedRef = useRef(false);
  const tabRef = useRef(tab);
  tabRef.current = tab;

  const clearPlayback = useCallback(() => {
    playQueueRef.current = [];
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
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      try { wsRef.current.send(JSON.stringify({ type: 'end' })); } catch { /* noop */ }
    }
    teardown();
    setStatus('idle');
    setSpeaking(false);
  }, [teardown]);

  const start = useCallback(async () => {
    if (status === 'connecting' || status === 'live') return;
    stoppedRef.current = false;
    setError(null);
    setInputText('');
    setOutputText('');
    setActions([]);
    setStatus('connecting');

    try {
      playCtxRef.current = new (window.AudioContext || window.webkitAudioContext)();

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
      sourceRef.current = source;
      workletRef.current = worklet;

      const ws = new WebSocket(assistantSocketUrl(tabRef.current));
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
          case 'action':
            actionSeqRef.current += 1;
            setActions((prev) => [
              ...prev,
              { id: actionSeqRef.current, name: msg.name, message: msg.message },
            ]);
            break;
          case 'interrupted':
            clearPlayback();
            break;
          case 'turn_complete':
            setInputText('');
            setOutputText('');
            break;
          case 'error':
            setError(msg.message || 'Assistant error');
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
  }, [status, enqueueAudio, clearPlayback, teardown]);

  useEffect(() => () => teardown(), [teardown]);

  const dismissAction = useCallback((id) => {
    setActions((prev) => prev.filter((a) => a.id !== id));
  }, []);

  const listening = status === 'live' && !speaking;

  return { status, error, speaking, listening, inputText, outputText, actions, dismissAction, start, stop };
}

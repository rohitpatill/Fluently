import { useState } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { toast } from 'sonner';
import * as api from '../api';
import { useModelTiers } from '../hooks/useApi';
import { PersonaAvatar, TierCard, Spinner } from './Shared';

const RELATIONS = ['Best friend', 'Mentor', 'Girlfriend', 'Boyfriend', 'Teacher'];

export default function Onboarding({ onComplete }) {
  const [step, setStep] = useState(1);
  const [name, setName] = useState('');
  const [relation, setRelation] = useState('');
  const [customRelation, setCustomRelation] = useState('');
  const [personality, setPersonality] = useState('');
  const [userName, setUserName] = useState('');
  const [userAbout, setUserAbout] = useState('');
  const [saving, setSaving] = useState(false);

  const effectiveRelation = customRelation.trim() || relation;
  const canNext = name.trim().length > 0 && effectiveRelation;

  async function goNext() {
    if (!canNext) return;
    setSaving(true);
    try {
      await api.putPersonaForm({
        name: name.trim(),
        relation: effectiveRelation,
        personality: personality.trim(),
        speaking_style: '',
      });
      setStep(2);
    } catch (err) {
      toast.error(err.message || 'Could not save persona');
    } finally {
      setSaving(false);
    }
  }

  // Step 3 ("brain") owns the actual finish: it stores the key+tier, THEN submits the
  // name + "about you" (so the LLM structuring of "about" uses the user's own key).
  async function finishWithModel() {
    setSaving(true);
    try {
      await api.submitOnboarding(userName.trim(), userAbout.trim());
      onComplete();
    } catch (err) {
      toast.error(err.message || 'Could not finish setup');
      setSaving(false); // stay so they can retry; leave the overlay only on success
    }
  }

  // The warm "getting to know you" overlay — now shown at the true finish (step 3),
  // powered by the user's just-configured key.
  const structuring = saving && step === 3;

  return (
    <div className="min-h-dvh bg-linear-to-b from-bg to-accent-soft flex items-center justify-center animate-fade-in overflow-y-auto px-4 py-6">
      <AnimatePresence>
        {structuring && (
          <motion.div
            key="structuring"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 flex flex-col items-center justify-center gap-6 bg-bg/85 backdrop-blur-sm"
          >
            <motion.div
              animate={{ scale: [1, 1.08, 1] }}
              transition={{ duration: 1.6, repeat: Infinity, ease: 'easeInOut' }}
            >
              <PersonaAvatar name={name} size="md" />
            </motion.div>
            <div className="text-center">
              <div className="text-lg font-semibold text-text">
                {name.trim() || 'They'} is getting to know you…
              </div>
              <div className="mt-1.5 text-sm text-muted flex items-center justify-center gap-1">
                remembering what matters
                <span className="inline-flex gap-0.5">
                  {[0, 1, 2].map((i) => (
                    <motion.span
                      key={i}
                      className="w-1 h-1 rounded-full bg-accent"
                      animate={{ opacity: [0.2, 1, 0.2] }}
                      transition={{ duration: 1.1, repeat: Infinity, delay: i * 0.2 }}
                    />
                  ))}
                </span>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
      <div className="w-[620px] max-w-full flex flex-col gap-6">
        <div className="flex items-center gap-2">
          <div className="w-[26px] h-[5px] rounded-full bg-accent" />
          <div className={`w-[26px] h-[5px] rounded-full transition-colors ${step >= 2 ? 'bg-accent' : 'bg-[#DDE0EA]'}`} />
          <div className={`w-[26px] h-[5px] rounded-full transition-colors ${step >= 3 ? 'bg-accent' : 'bg-[#DDE0EA]'}`} />
          <span className="text-xs text-muted-2 ml-2">Step {step} of 3</span>
        </div>

        <AnimatePresence mode="wait">
          {step === 1 && (
            <motion.div
              key="step1"
              initial={{ opacity: 0, x: 12 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -12 }}
              className="flex flex-col gap-6"
            >
              <div>
                <h1 className="m-0 text-[32px] sm:text-4xl font-bold tracking-tight leading-tight">
                  Someone is waiting
                  <br />
                  to meet you.
                </h1>
                <p className="mt-3 mb-0 text-base text-[#6B7080] font-serif-italic">
                  Give them a name, a role in your life, a soul. You can change everything later.
                </p>
              </div>

              <div className="flex flex-col gap-4">
                <div className="bg-surface border border-border-2 rounded-2xl px-5 py-3.5 shadow-soft">
                  <div className="text-[11px] font-semibold tracking-wider uppercase text-muted-2">
                    Their name
                  </div>
                  <input
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    placeholder="Jack"
                    className="border-none outline-none text-xl font-semibold mt-1 w-full bg-transparent text-text"
                  />
                </div>

                <div>
                  <div className="text-[11px] font-semibold tracking-wider uppercase text-muted-2 mb-2.5">
                    Who are they to you?
                  </div>
                  <div className="flex gap-2.5 flex-wrap">
                    {RELATIONS.map((r) => (
                      <button
                        key={r}
                        onClick={() => {
                          setRelation(r);
                          setCustomRelation('');
                        }}
                        className={`rounded-full px-4.5 py-2 text-[13.5px] cursor-pointer transition-colors ${
                          relation === r && !customRelation
                            ? 'bg-accent text-white font-semibold shadow-accent border-none'
                            : 'bg-surface text-text-3 border border-border-2'
                        }`}
                      >
                        {r}
                      </button>
                    ))}
                    <input
                      value={customRelation}
                      onChange={(e) => {
                        setCustomRelation(e.target.value);
                        if (e.target.value) setRelation('');
                      }}
                      placeholder="something else…"
                      className="bg-surface border border-dashed border-[#C9CDD8] rounded-full px-4.5 py-2 text-[13.5px] text-text-3 outline-none w-[130px]"
                    />
                  </div>
                </div>

                <div className="bg-surface border border-border-2 rounded-2xl px-5 py-3.5 shadow-soft">
                  <div className="text-[11px] font-semibold tracking-wider uppercase text-muted-2">
                    Personality, age, how they talk, your shared history…
                  </div>
                  <textarea
                    value={personality}
                    onChange={(e) => setPersonality(e.target.value)}
                    placeholder="28, dry sense of humor, brutally honest but always on my side…"
                    className="border-none outline-none resize-none text-[14.5px] leading-relaxed text-text-3 mt-2 w-full h-16 bg-transparent font-sans"
                  />
                </div>
              </div>

              <div className="flex justify-end">
                <button
                  onClick={goNext}
                  disabled={!canNext || saving}
                  className="w-full sm:w-auto bg-accent hover:bg-accent-hover disabled:opacity-55 disabled:cursor-not-allowed text-white border-none rounded-2xl px-7.5 py-3.5 text-[15px] font-semibold shadow-accent-lg cursor-pointer transition-colors"
                >
                  {saving ? 'Saving…' : `Bring ${name.trim() || 'them'} to life →`}
                </button>
              </div>
            </motion.div>
          )}

          {step === 2 && (
            <motion.div
              key="step2"
              initial={{ opacity: 0, x: 12 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -12 }}
              className="flex flex-col gap-6"
            >
              <div className="flex gap-3.5 items-start animate-msg-in">
                <PersonaAvatar name={name} size="md" />
                <div className="bg-surface border border-border rounded-[4px_18px_18px_18px] px-5 py-4 text-[15.5px] leading-relaxed text-text-2 shadow-soft">
                  Hey — I'm {name.trim() || 'your companion'}. Apparently we go way back. Before we
                  start talking every day: what should I call you, and what should I know?
                </div>
              </div>

              <div className="flex flex-col gap-4">
                <div className="bg-surface border border-border-2 rounded-2xl px-5 py-3.5 shadow-soft">
                  <div className="text-[11px] font-semibold tracking-wider uppercase text-muted-2">
                    Your name
                  </div>
                  <input
                    value={userName}
                    onChange={(e) => setUserName(e.target.value)}
                    placeholder="Aarav"
                    className="border-none outline-none text-xl font-semibold mt-1 w-full bg-transparent text-text"
                  />
                </div>
                <div className="bg-surface border border-border-2 rounded-2xl px-5 py-3.5 shadow-soft">
                  <div className="text-[11px] font-semibold tracking-wider uppercase text-muted-2">
                    About you — optional, {name.trim() || 'they'} learns the rest by talking
                  </div>
                  <textarea
                    value={userAbout}
                    onChange={(e) => setUserAbout(e.target.value)}
                    placeholder="Founder, 26, want my English to sound natural in meetings…"
                    className="border-none outline-none resize-none text-[14.5px] leading-relaxed text-text-3 mt-2 w-full h-14 bg-transparent font-sans"
                  />
                </div>
              </div>

              <div className="flex flex-col-reverse sm:flex-row sm:justify-between sm:items-center gap-3">
                <button onClick={() => setStep(1)} className="bg-transparent border-none text-[13.5px] text-muted-2 cursor-pointer">
                  ← Back
                </button>
                <button
                  onClick={() => userName.trim() && setStep(3)}
                  disabled={!userName.trim()}
                  className="w-full sm:w-auto bg-accent hover:bg-accent-hover disabled:opacity-55 disabled:cursor-not-allowed text-white border-none rounded-2xl px-7.5 py-3.5 text-[15px] font-semibold shadow-accent-lg cursor-pointer transition-colors"
                >
                  One last thing →
                </button>
              </div>
            </motion.div>
          )}

          {step === 3 && (
            <motion.div
              key="step3"
              initial={{ opacity: 0, x: 12 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -12 }}
            >
              <BrainStep
                personaName={name}
                onBack={() => setStep(2)}
                onReady={finishWithModel}
                busy={saving}
                ctaLabel={`Start talking to ${name.trim() || 'them'} ✦`}
              />
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}

// ── Brain step: paste key → verify → tier cards appear → pick → Continue ─────────────
// Progressive reveal: no cards until the key verifies; no Continue until a card is picked.
// Reused by App's standalone model-config gate (persona set, but no key yet).
export function BrainStep({ personaName, onBack, onReady, busy = false, ctaLabel = 'Continue ✦' }) {
  const tiers = useModelTiers();
  const [apiKey, setApiKey] = useState('');
  const [verifying, setVerifying] = useState(false);
  const [verified, setVerified] = useState(false); // becomes true once ANY tier's key check passed
  const [tier, setTier] = useState('');

  // We verify by calling POST /api/model/key with the default (swift) tier — it both checks
  // the key AND stores it. Once verified, picking a card + Continue just switches the tier.
  async function verify() {
    const key = apiKey.trim();
    if (!key) return;
    setVerifying(true);
    try {
      const status = await api.setModelKey(key, 'swift');
      setVerified(true);
      setTier(status.tier || 'swift');
    } catch (err) {
      toast.error(err.message || "That key didn't work — double-check it and try again.");
      setVerified(false);
    } finally {
      setVerifying(false);
    }
  }

  async function proceed() {
    if (!verified || !tier) return;
    try {
      // Make sure the stored tier matches the card the user picked (verify stored swift).
      await api.setModelTier(tier);
    } catch (err) {
      toast.error(err.message || 'Could not set your tier');
      return;
    }
    onReady?.();
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="m-0 text-[30px] sm:text-4xl font-bold tracking-tight leading-tight">
          How smart should
          <br />I be?
        </h1>
        <p className="mt-3 mb-0 text-base text-[#6B7080] font-serif-italic">
          {personaName?.trim() || 'Your companion'} runs on your own Google Gemini key — it stays
          yours, encrypted, and powers every conversation.
        </p>
      </div>

      {/* Key input + verify */}
      <div className="bg-surface border border-border-2 rounded-2xl px-5 py-3.5 shadow-soft">
        <div className="text-[11px] font-semibold tracking-wider uppercase text-muted-2">
          Your Gemini API key
        </div>
        <div className="flex items-center gap-2 mt-1">
          <input
            type="password"
            value={apiKey}
            onChange={(e) => {
              setApiKey(e.target.value);
              setVerified(false);
              setTier('');
            }}
            placeholder="AIza…"
            className="border-none outline-none text-[15px] font-mono flex-1 w-full bg-transparent text-text"
          />
          <button
            onClick={verify}
            disabled={!apiKey.trim() || verifying || verified}
            className="shrink-0 bg-accent hover:bg-accent-hover disabled:opacity-55 disabled:cursor-not-allowed text-white border-none rounded-xl px-4 py-2 text-[13.5px] font-semibold cursor-pointer transition-colors"
          >
            {verifying ? 'Checking…' : verified ? '✓ Verified' : 'Verify'}
          </button>
        </div>
      </div>

      {/* Tier cards — revealed only after the key verifies */}
      <AnimatePresence>
        {verified && (
          <motion.div
            key="tiers"
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            className="flex flex-col gap-3"
          >
            <div className="text-[13px] text-muted-2">Now pick your brain:</div>
            {tiers.isLoading ? (
              <div className="flex justify-center py-6"><Spinner /></div>
            ) : (
              <div className="grid sm:grid-cols-2 gap-3">
                {(tiers.data || []).map((t) => (
                  <TierCard key={t.key} tier={t} selected={tier === t.key} onSelect={setTier} />
                ))}
              </div>
            )}
          </motion.div>
        )}
      </AnimatePresence>

      <div className="flex flex-col-reverse sm:flex-row sm:justify-between sm:items-center gap-3">
        {onBack && (
          <button onClick={onBack} className="bg-transparent border-none text-[13.5px] text-muted-2 cursor-pointer">
            ← Back
          </button>
        )}
        {/* Continue only appears once a tier is selected */}
        <AnimatePresence>
          {verified && tier && (
            <motion.button
              key="cta"
              initial={{ opacity: 0, scale: 0.96 }}
              animate={{ opacity: 1, scale: 1 }}
              onClick={proceed}
              disabled={busy}
              className="w-full sm:w-auto sm:ml-auto bg-accent hover:bg-accent-hover disabled:opacity-55 disabled:cursor-not-allowed text-white border-none rounded-2xl px-7.5 py-3.5 text-[15px] font-semibold shadow-accent-lg cursor-pointer transition-colors"
            >
              {busy ? 'Starting…' : ctaLabel}
            </motion.button>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}

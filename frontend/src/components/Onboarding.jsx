import { useState } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { toast } from 'sonner';
import * as api from '../api';
import { PersonaAvatar } from './Shared';

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

  async function finish() {
    if (!userName.trim()) return;
    setSaving(true);
    try {
      // Backend stores the name and LLM-structures the free-text "about you"
      // into clean entries across identity / memory / persona.
      await api.submitOnboarding(userName.trim(), userAbout.trim());
      onComplete();
    } catch (err) {
      toast.error(err.message || 'Could not save your info');
    } finally {
      setSaving(false);
    }
  }

  // While the "about you" dump is being structured, show a warm "getting to know you" overlay.
  const structuring = saving && step === 2 && userAbout.trim().length > 0;

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
          <div className={`w-[26px] h-[5px] rounded-full transition-colors ${step === 2 ? 'bg-accent' : 'bg-[#DDE0EA]'}`} />
          <span className="text-xs text-muted-2 ml-2">Step {step} of 2</span>
        </div>

        <AnimatePresence mode="wait">
          {step === 1 ? (
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
          ) : (
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
                  onClick={finish}
                  disabled={!userName.trim() || saving}
                  className="w-full sm:w-auto bg-accent hover:bg-accent-hover disabled:opacity-55 disabled:cursor-not-allowed text-white border-none rounded-2xl px-7.5 py-3.5 text-[15px] font-semibold shadow-accent-lg cursor-pointer transition-colors"
                >
                  {saving ? 'Starting…' : `Start talking to ${name.trim() || 'them'} ✦`}
                </button>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}

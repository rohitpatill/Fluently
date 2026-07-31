import { useQuery } from '@tanstack/react-query';
import * as api from '../api';

// The backend is on a free host that SLEEPS when idle, so the very first request of a session
// can take 20-30s (cold start) or fail once before the container is up. With `retry: 0` a single
// failed probe flipped the whole app to the error screen — a working app looked dead. So we retry
// with a capped backoff (~26s of attempts) and only surface an error once that budget is spent.
// `<BootScreen>` covers the wait and narrates it, so the retries are never a blank screen.
// A cold start can genuinely take a MINUTE (container boot + Mongo connect), so the budget has
// to cover the worst case, not the average — erroring at 26s showed "we're having a moment" for
// a backend that was simply still booting. 12 attempts with a 2s..10s backoff ≈ 105s of waiting.
// The cost of being generous is only a longer BootScreen (which narrates the wait); the cost of
// being stingy is a working app that looks dead. So we err long.
const HEALTH_MAX_RETRIES = 12;

export function useHealth() {
  return useQuery({
    queryKey: ['health'],
    queryFn: api.getHealth,
    retry: HEALTH_MAX_RETRIES,
    // 2s,4s,8s,10s,10s… — capped at 10s so late attempts stay responsive once it wakes.
    retryDelay: (attempt) => Math.min(2000 * 2 ** attempt, 10000),
    staleTime: 0,
    refetchInterval: 15000,
  });
}

export function useMe() {
  return useQuery({
    queryKey: ['me'],
    queryFn: api.getMe,
    retry: false, // a 401 means "logged out" — resolve fast, don't retry
    staleTime: 60_000,
  });
}

export function usePersonaMemory({ enabled = true } = {}) {
  return useQuery({
    queryKey: ['memory', 'persona'],
    queryFn: () => api.getMemory('persona'),
    enabled,
  });
}

// Persona-scoped key: switching the active persona reads a DIFFERENT cache entry, so the
// previous persona's list can never briefly flash before the refetch. Invalidating the bare
// ['conversations'] prefix still refreshes every persona's list (prefix match), so existing
// invalidations keep working unchanged.
export function useConversations(personaId) {
  return useQuery({
    queryKey: ['conversations', personaId ?? null],
    queryFn: api.listConversations,
  });
}

export function useMessages(conversationId) {
  return useQuery({
    queryKey: ['messages', conversationId],
    queryFn: () => api.getConversationMessages(conversationId),
    enabled: !!conversationId,
  });
}

export function useWords() {
  return useQuery({
    queryKey: ['words'],
    queryFn: api.listWords,
  });
}

export function useDashboardStats() {
  return useQuery({
    queryKey: ['dashboard'],
    queryFn: api.getDashboardStats,
  });
}

export function useWordEvents(wordId, enabled) {
  return useQuery({
    queryKey: ['word-events', wordId],
    queryFn: () => api.getWordEvents(wordId),
    enabled: !!wordId && !!enabled,
  });
}

export function useMemoryFile(file, { enabled = true } = {}) {
  return useQuery({
    queryKey: ['memory', file],
    queryFn: () => api.getMemory(file),
    enabled,
  });
}

export function usePersonas({ enabled = true } = {}) {
  return useQuery({
    queryKey: ['personas'],
    queryFn: api.listPersonas,
    enabled,
  });
}

// The curated Discover catalog — static per deployment, cache aggressively.
export function usePersonaCatalog({ enabled = true } = {}) {
  return useQuery({
    queryKey: ['persona-catalog'],
    queryFn: api.getPersonaCatalog,
    enabled,
    staleTime: Infinity,
  });
}

// The Swift/Sage catalogue — static per deployment, cache aggressively.
export function useModelTiers({ enabled = true } = {}) {
  return useQuery({
    queryKey: ['model-tiers'],
    queryFn: api.getModelTiers,
    enabled,
    staleTime: Infinity,
  });
}

// Whether voice mode is available for this user (they've configured a BYO key + tier).
export function useVoiceStatus({ enabled = true } = {}) {
  return useQuery({
    queryKey: ['voice-status'],
    queryFn: api.getVoiceStatus,
    enabled,
    staleTime: 60_000,
  });
}

// The voice catalogue (names + tone descriptors + gender) for the persona-form picker.
export function useVoices({ enabled = true } = {}) {
  return useQuery({
    queryKey: ['voices'],
    queryFn: api.getVoices,
    enabled,
    staleTime: Infinity,
  });
}

// Whether the Fluently in-app voice assistant is available (same gate as voice: BYO key + tier).
export function useAssistantStatus({ enabled = true } = {}) {
  return useQuery({
    queryKey: ['assistant-status'],
    queryFn: api.getAssistantStatus,
    enabled,
    staleTime: 60_000,
  });
}

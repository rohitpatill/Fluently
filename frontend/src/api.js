// The one backend base URL, read from the frontend .env (VITE_API_URL).
// Every endpoint below is built from this. Change it in .env to deploy.
const BASE_URL = import.meta.env.VITE_API_URL;

class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.status = status;
  }
}

async function request(path, options = {}) {
  let res;
  try {
    res = await fetch(`${BASE_URL}${path}`, {
      credentials: 'include', // send/receive the session cookie cross-origin
      headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
      ...options,
    });
  } catch (err) {
    throw new ApiError('Could not reach the server. Is the backend running?', 0);
  }
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail || detail;
    } catch {
      /* ignore */
    }
    throw new ApiError(detail, res.status);
  }
  if (res.status === 204) return null;
  const text = await res.text();
  return text ? JSON.parse(text) : null;
}

// ---------- Auth ----------
export const getMe = () => request('/api/auth/me');

export const logout = () => request('/api/auth/logout', { method: 'POST' });

// Full-page redirect into the backend's Google login (which redirects on to Google).
export const loginWithGoogle = () => {
  window.location.href = `${BASE_URL}/api/auth/google/login`;
};

// ---------- Conversations ----------
export const createConversation = (opts = {}) =>
  request('/api/conversations', { method: 'POST', body: JSON.stringify(opts) });

export const listConversations = () => request('/api/conversations');

export const getConversation = (id) => request(`/api/conversations/${id}`);

export const getConversationMessages = (id) => request(`/api/conversations/${id}/messages`);

export const deleteConversation = (id) => request(`/api/conversations/${id}`, { method: 'DELETE' });

export const setConversationCategory = (id, category) =>
  request(`/api/conversations/${id}/category?category=${encodeURIComponent(category)}`, {
    method: 'PATCH',
  });

export const requestOpener = (id) =>
  request(`/api/conversations/${id}/opener`, { method: 'POST' });

export const suggestTopics = (id) =>
  request(`/api/conversations/${id}/topics`, { method: 'POST' });

export const searchConversations = (params) =>
  request('/api/conversations/search', { method: 'POST', body: JSON.stringify(params) });

// ---------- Chat ----------
export const sendChatMessage = (conversationId, content) =>
  request(`/api/chat/${conversationId}`, { method: 'POST', body: JSON.stringify({ content }) });

// ---------- Words ----------
export const listWords = () => request('/api/words');

export const addWord = (text, kind) =>
  request('/api/words', { method: 'POST', body: JSON.stringify({ text, kind }) });

export const adjustWord = (id, delta, reason) =>
  request(`/api/words/${id}/adjust`, { method: 'POST', body: JSON.stringify({ delta, reason }) });

export const setWordNote = (id, note) =>
  request(`/api/words/${id}/note`, { method: 'PUT', body: JSON.stringify({ note }) });

export const deleteWord = (id) => request(`/api/words/${id}`, { method: 'DELETE' });

export const getWordEvents = (id) => request(`/api/words/${id}/events`);

// ---------- Memory ----------
export const getMemory = (file) => request(`/api/memory/${file}`);

export const putMemoryRaw = (file, raw) =>
  request(`/api/memory/${file}/raw`, { method: 'PUT', body: JSON.stringify({ raw }) });

export const appendMemoryLine = (file, text) =>
  request(`/api/memory/${file}/lines`, { method: 'POST', body: JSON.stringify({ text }) });

// Edit a memory file by text (old_string -> new_string; empty new_string deletes).
export const editMemory = (file, oldString, newString, replaceAll = false) =>
  request(`/api/memory/${file}/edit`, {
    method: 'POST',
    body: JSON.stringify({ old_string: oldString, new_string: newString, replace_all: replaceAll }),
  });

export const putPersonaForm = (data) =>
  request('/api/memory/persona/form', { method: 'PUT', body: JSON.stringify(data) });

// Finish onboarding: name + free-text "about you" -> LLM-structured across the 3 memory files.
export const submitOnboarding = (name, about) =>
  request('/api/memory/onboarding', { method: 'POST', body: JSON.stringify({ name, about }) });

// ---------- Personas (multi-persona) ----------
export const listPersonas = () => request('/api/personas');

export const createPersona = (data) =>
  request('/api/personas', { method: 'POST', body: JSON.stringify(data) });

export const editPersona = (id, data) =>
  request(`/api/personas/${id}`, { method: 'PUT', body: JSON.stringify(data) });

export const setPersonaAvatar = (id, avatarUrl) =>
  request(`/api/personas/${id}/avatar`, {
    method: 'PUT',
    body: JSON.stringify({ avatar_url: avatarUrl }),
  });

export const activatePersona = (id) =>
  request(`/api/personas/${id}/activate`, { method: 'POST' });

export const deletePersona = (id) => request(`/api/personas/${id}`, { method: 'DELETE' });

// Discover: curated public-persona catalog + "use" (copies one into the user's personas).
export const getPersonaCatalog = () => request('/api/personas/catalog');

export const usePersonaFromCatalog = (catalogId) =>
  request(`/api/personas/catalog/${catalogId}/use`, { method: 'POST' });

// ---------- Voice mode (real-time audio via Gemini Live) ----------
export const getVoices = () => request('/api/voice/voices');

export const getVoiceStatus = () => request('/api/voice/status');

// The WebSocket URL for a conversation's voice session (derives ws:// from the http base).
export const voiceSocketUrl = (conversationId) => {
  const wsBase = BASE_URL.replace(/^http/, 'ws');
  return `${wsBase}/api/voice/ws/${conversationId}`;
};

// ---------- Fluently voice assistant (in-app help + hands-free actions) ----------
export const getAssistantStatus = () => request('/api/assistant/status');

// The WebSocket URL for the Fluently assistant. `tab` tells the assistant which screen the
// user is currently on so it can ground its help. No conversation id — the session is ephemeral.
export const assistantSocketUrl = (tab) => {
  const wsBase = BASE_URL.replace(/^http/, 'ws');
  return `${wsBase}/api/assistant/ws?tab=${encodeURIComponent(tab || 'chat')}`;
};

// ---------- Model (bring-your-own-key + Swift/Sage tiers) ----------
export const getModelTiers = () => request('/api/model/tiers');

export const getModelStatus = () => request('/api/model/status');

// Verify + store the key for a tier (used by onboarding AND Settings 'replace key').
export const setModelKey = (apiKey, tier) =>
  request('/api/model/key', { method: 'POST', body: JSON.stringify({ api_key: apiKey, tier }) });

// Switch tier with the already-stored key (Settings Swift↔Sage toggle).
export const setModelTier = (tier) =>
  request('/api/model/tier', { method: 'PUT', body: JSON.stringify({ tier }) });

// ---------- Settings / data management (HARD deletes) ----------
// personaId omitted → delete every persona's chats; given → only that persona's.
export const purgeConversations = (personaId) =>
  request(
    `/api/settings/conversations${personaId ? `?persona_id=${encodeURIComponent(personaId)}` : ''}`,
    { method: 'DELETE' },
  );

export const purgeMemories = () => request('/api/settings/memories', { method: 'DELETE' });

export const purgeAll = (keepWords) =>
  request('/api/settings/purge-all', { method: 'POST', body: JSON.stringify({ keep_words: keepWords }) });

// ---------- Dashboard ----------
export const getDashboardStats = () => request('/api/dashboard/stats');

export const getHealth = () => request('/api/health');

export { ApiError };

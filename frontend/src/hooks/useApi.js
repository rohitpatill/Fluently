import { useQuery } from '@tanstack/react-query';
import * as api from '../api';

export function useHealth() {
  return useQuery({
    queryKey: ['health'],
    queryFn: api.getHealth,
    retry: 0,
    staleTime: 0,
    refetchInterval: 15000,
  });
}

export function usePersonaMemory() {
  return useQuery({
    queryKey: ['memory', 'persona'],
    queryFn: () => api.getMemory('persona'),
  });
}

export function useConversations() {
  return useQuery({
    queryKey: ['conversations'],
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

export function useMemoryFile(file) {
  return useQuery({
    queryKey: ['memory', file],
    queryFn: () => api.getMemory(file),
  });
}

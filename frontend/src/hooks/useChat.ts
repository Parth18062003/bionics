/**
 * AADAP — useChat Hook
 * ======================
 * React hook for chat functionality with SSE streaming.
 */

import { useState, useCallback, useRef, useEffect } from 'react';
import type {
  ChatSession,
  ExtractedRequirements,
  RequirementsUpdateRequest,
  SSEEvent,
  SessionCreateResponse,
  TaskCreateResponse,
} from '@/types/chat';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export function useChat() {
  const [session, setSession] = useState<ChatSession | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  // Load session from localStorage on mount
  useEffect(() => {
    const savedSessionId = localStorage.getItem('chat_session_id');
    if (savedSessionId && !session) {
      fetchSession(savedSessionId);
    }
  }, []);

  // Save session ID to localStorage
  useEffect(() => {
    if (session?.session_id) {
      localStorage.setItem('chat_session_id', session.session_id);
    }
  }, [session?.session_id]);

  const fetchSession = useCallback(async (sessionId: string) => {
    try {
      const response = await fetch(`${API_BASE}/api/chat/sessions/${sessionId}`);
      if (response.ok) {
        const data = await response.json();
        setSession(data);
      } else {
        // Session not found, clear from localStorage
        localStorage.removeItem('chat_session_id');
      }
    } catch (err) {
      console.error('Failed to fetch session:', err);
    }
  }, []);

  const createSession = useCallback(async () => {
    try {
      setError(null);
      const response = await fetch(`${API_BASE}/api/chat/sessions`, {
        method: 'POST',
      });

      if (!response.ok) {
        throw new Error('Failed to create session');
      }

      const data: SessionCreateResponse = await response.json();
      
      // Fetch the full session
      await fetchSession(data.session_id);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to create session';
      setError(message);
    }
  }, [fetchSession]);

  const sendMessage = useCallback(async (content: string) => {
    if (!session?.session_id) {
      setError('No active session');
      return;
    }

    setIsLoading(true);
    setError(null);

    // Add user message optimistically
    const userMessage = {
      role: 'user' as const,
      content,
      timestamp: new Date().toISOString(),
    };
    setSession(prev => prev ? {
      ...prev,
      messages: [...prev.messages, userMessage],
    } : null);

    // Create abort controller for this request
    abortControllerRef.current = new AbortController();

    try {
      const response = await fetch(
        `${API_BASE}/api/chat/sessions/${session.session_id}/messages`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ message: content }),
          signal: abortControllerRef.current.signal,
        }
      );

      if (!response.ok) {
        throw new Error('Failed to send message');
      }

      // Process SSE stream
      const reader = response.body?.getReader();
      const decoder = new TextDecoder();
      let assistantContent = '';

      if (!reader) {
        throw new Error('No response body');
      }

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value);
        const lines = chunk.split('\n');

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const event: SSEEvent = JSON.parse(line.slice(6));

              if (event.type === 'content' && event.content) {
                assistantContent += event.content;
                
                // Update assistant message in real-time
                setSession(prev => {
                  if (!prev) return null;
                  const messages = [...prev.messages];
                  const lastMessage = messages[messages.length - 1];
                  
                  if (lastMessage?.role === 'assistant') {
                    lastMessage.content = assistantContent;
                  } else {
                    messages.push({
                      role: 'assistant',
                      content: assistantContent,
                      timestamp: new Date().toISOString(),
                    });
                  }
                  
                  return { ...prev, messages };
                });
              }

              if (event.type === 'requirements' && event.requirements) {
                setSession(prev => prev ? {
                  ...prev,
                  current_requirements: event.requirements!,
                } : null);
              }

              if (event.type === 'error') {
                setError(event.message || 'Stream error');
              }
            } catch {
              // Ignore parse errors for incomplete JSON
            }
          }
        }
      }
    } catch (err) {
      if (err instanceof Error && err.name === 'AbortError') {
        // Request was cancelled, ignore
        return;
      }
      const message = err instanceof Error ? err.message : 'Failed to send message';
      setError(message);
    } finally {
      setIsLoading(false);
      abortControllerRef.current = null;
    }
  }, [session?.session_id]);

  const updateRequirements = useCallback(async (updates: RequirementsUpdateRequest) => {
    if (!session?.session_id) {
      setError('No active session');
      return;
    }

    try {
      setError(null);
      const response = await fetch(
        `${API_BASE}/api/chat/sessions/${session.session_id}/requirements`,
        {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(updates),
        }
      );

      if (!response.ok) {
        throw new Error('Failed to update requirements');
      }

      const data = await response.json();
      setSession(data);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to update requirements';
      setError(message);
    }
  }, [session?.session_id]);

  const createTask = useCallback(async (): Promise<TaskCreateResponse | null> => {
    if (!session?.session_id) {
      setError('No active session');
      return null;
    }

    try {
      setError(null);
      const response = await fetch(
        `${API_BASE}/api/chat/sessions/${session.session_id}/create-task`,
        { method: 'POST' }
      );

      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.detail || 'Failed to create task');
      }

      const data: TaskCreateResponse = await response.json();
      
      // Clear session after task creation
      localStorage.removeItem('chat_session_id');
      setSession(null);
      
      return data;
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to create task';
      setError(message);
      return null;
    }
  }, [session?.session_id]);

  const resetSession = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    localStorage.removeItem('chat_session_id');
    setSession(null);
    setError(null);
    setIsLoading(false);
  }, []);

  return {
    session,
    isLoading,
    error,
    createSession,
    sendMessage,
    updateRequirements,
    createTask,
    resetSession,
  };
}

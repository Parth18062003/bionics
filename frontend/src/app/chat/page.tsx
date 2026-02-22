/**
 * AADAP — Chat Page
 * ====================
 * Dedicated chat page with split view layout.
 */

'use client';

import { useEffect, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useChat } from '@/hooks/useChat';
import { ChatMessage } from '@/components/chat/ChatMessage';
import { ChatInput } from '@/components/chat/ChatInput';
import { RequirementsPanel } from '@/components/chat/RequirementsPanel';

export default function ChatPage() {
  const router = useRouter();
  const {
    session,
    isLoading,
    error,
    createSession,
    sendMessage,
    updateRequirements,
    createTask,
    resetSession,
  } = useChat();

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const [isCreating, setIsCreating] = useState(false);
  const [taskCreated, setTaskCreated] = useState<{ taskId: string; redirectUrl: string } | null>(null);

  // Create session on mount
  useEffect(() => {
    if (!session) {
      createSession();
    }
  }, [session, createSession]);

  // Auto-scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [session?.messages]);

  const handleCreateTask = async () => {
    setIsCreating(true);
    try {
      const result = await createTask();
      if (result) {
        setTaskCreated({ taskId: result.task_id, redirectUrl: result.redirect_url });
      }
    } finally {
      setIsCreating(false);
    }
  };

  // Task created success modal
  if (taskCreated) {
    return (
      <div className="h-screen flex items-center justify-center bg-gray-50 dark:bg-gray-950">
        <div className="bg-white dark:bg-gray-900 rounded-xl shadow-lg p-8 max-w-md text-center">
          <div className="w-16 h-16 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-4">
            <svg className="w-8 h-8 text-green-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
            </svg>
          </div>
          <h2 className="text-xl font-semibold text-gray-900 dark:text-white mb-2">
            Task Created!
          </h2>
          <p className="text-gray-500 mb-6">
            Your task has been created successfully.
          </p>
          <div className="flex gap-3">
            <button
              onClick={() => router.push(taskCreated.redirectUrl)}
              className="flex-1 py-2 px-4 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
            >
              View Task
            </button>
            <button
              onClick={() => {
                setTaskCreated(null);
                resetSession();
                createSession();
              }}
              className="flex-1 py-2 px-4 bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300 rounded-lg hover:bg-gray-200 dark:hover:bg-gray-700"
            >
              Create Another
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="h-[calc(100vh-60px)] flex flex-col md:flex-row">
      {/* Chat Section */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Header */}
        <div className="p-4 border-b border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900">
          <div className="flex items-center justify-between">
            <h1 className="text-xl font-semibold text-gray-900 dark:text-white">
              Chat
            </h1>
            <button
              onClick={() => {
                resetSession();
                createSession();
              }}
              className="text-sm text-blue-600 hover:text-blue-700"
            >
              New Chat
            </button>
          </div>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto p-4 bg-gray-50 dark:bg-gray-950">
          {!session?.messages.length && !isLoading && (
            <div className="text-center text-gray-500 dark:text-gray-400 mt-20">
              <p className="text-lg mb-2">Start a conversation</p>
              <p className="text-sm">
                Describe your data engineering task in natural language.
              </p>
            </div>
          )}
          {session?.messages.map((message, index) => (
            <ChatMessage key={index} message={message} />
          ))}
          {isLoading && (
            <div className="flex justify-start mb-4">
              <div className="bg-gray-100 dark:bg-gray-800 rounded-lg px-4 py-3">
                <div className="flex gap-1">
                  <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                  <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                  <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                </div>
              </div>
            </div>
          )}
          {error && (
            <div className="text-center text-red-500 py-4">
              {error}
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* Input */}
        <ChatInput
          onSend={sendMessage}
          disabled={isLoading || !session}
          placeholder="Describe your task..."
        />
      </div>

      {/* Requirements Panel */}
      <div className="w-full md:w-96 flex-shrink-0 border-t md:border-t-0 md:border-l border-gray-200 dark:border-gray-700">
        <RequirementsPanel
          requirements={session?.current_requirements ?? null}
          onUpdate={updateRequirements}
          onCreateTask={handleCreateTask}
          isCreating={isCreating}
        />
      </div>
    </div>
  );
}

'use client';

import { useEffect, useRef } from 'react';

import { ChoiceButtons } from '@/components/ChoiceButtons';
import type { ChatMessage } from '@/features/chat/chat.types';
import { ChatInput } from '@/features/chat/ChatInput';
import { MessageBubble } from '@/features/chat/MessageBubble';

interface ChatPanelProps {
  messages: ChatMessage[];
  choices: string[];
  inputText: string;
  onInputChange: (text: string) => void;
  onChoice: (choice: string) => void;
  onSend: (text: string) => void;
  onFileSelect?: (file: File) => void;
  isStreaming?: boolean;
  isUploading?: boolean;
  statusText?: string | null;
}

export const ChatPanel = ({
  messages,
  choices,
  inputText,
  onInputChange,
  onChoice,
  onSend,
  onFileSelect,
  isStreaming = false,
  isUploading = false,
  statusText,
}: ChatPanelProps) => {
  const logRef = useRef<HTMLDivElement>(null);
  const lastText = messages[messages.length - 1]?.text;

  useEffect(() => {
    // 페이지가 아니라 대화 목록 칸만 맨 아래로 내립니다.
    const log = logRef.current;
    if (log) log.scrollTop = log.scrollHeight;
  }, [messages.length, choices.length, lastText, statusText]);

  return (
    <section
      aria-label="대화"
      className="border-line bg-canvas flex h-[70dvh] flex-col overflow-hidden rounded-2xl border lg:h-auto lg:min-h-0"
    >
      <div
        ref={logRef}
        className="flex min-h-0 flex-1 flex-col gap-4 overflow-y-auto p-4"
        role="log"
        aria-live="polite"
      >
        {messages.map((message) => (
          <MessageBubble key={message.id} message={message} />
        ))}
        {statusText && (
          <p role="status" className="text-muted text-sm">
            {statusText}
          </p>
        )}
        <ChoiceButtons choices={choices} onSelect={onChoice} isDisabled={isStreaming} />
      </div>
      <ChatInput
        value={inputText}
        onChange={onInputChange}
        onSend={onSend}
        onFileSelect={onFileSelect}
        isDisabled={isStreaming}
        isUploading={isUploading}
      />
    </section>
  );
};

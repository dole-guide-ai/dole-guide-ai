'use client';

import { useEffect, useRef } from 'react';

import { ChoiceButtons } from '@/components/ChoiceButtons';
import type { ChatMessage } from '@/features/chat/chat.types';
import { ChatInput } from '@/features/chat/ChatInput';
import { MessageBubble } from '@/features/chat/MessageBubble';

interface ChatPanelProps {
  messages: ChatMessage[];
  choices: string[];
  onChoice: (choice: string) => void;
  onSend: (text: string) => void;
  isInputDisabled?: boolean;
  inputDisabledReason?: string;
}

export const ChatPanel = ({
  messages,
  choices,
  onChoice,
  onSend,
  isInputDisabled = false,
  inputDisabledReason,
}: ChatPanelProps) => {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    // jsdom(테스트)에는 scrollIntoView가 없어서 있을 때만 호출합니다.
    bottomRef.current?.scrollIntoView?.({ block: 'end' });
  }, [messages.length, choices.length]);

  return (
    <section
      aria-label="대화"
      className="border-line bg-canvas flex min-h-[60vh] flex-col overflow-hidden rounded-2xl border"
    >
      <div className="flex flex-1 flex-col gap-4 overflow-y-auto p-4" role="log" aria-live="polite">
        {messages.map((message) => (
          <MessageBubble key={message.id} message={message} />
        ))}
        <ChoiceButtons choices={choices} onSelect={onChoice} />
        <div ref={bottomRef} />
      </div>
      <ChatInput
        onSend={onSend}
        isDisabled={isInputDisabled}
        disabledReason={inputDisabledReason}
      />
    </section>
  );
};

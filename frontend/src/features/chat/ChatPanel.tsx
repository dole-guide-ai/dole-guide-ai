'use client';

import { useEffect, useRef } from 'react';

import { Sparkles } from 'lucide-react';

import { ChoiceButtons } from '@/components/ChoiceButtons';
import type { ChatMessage } from '@/features/chat/chat.types';
import { ChatInput } from '@/features/chat/ChatInput';
import { MessageBubble } from '@/features/chat/MessageBubble';
import { ImportPicker } from '@/features/imports/ImportPicker';

import { ICON_SIZE, ICON_STROKE } from '@/lib/iconSize';
import type { ImportKind } from '@/types/imports.types';

interface ChatPanelProps {
  messages: ChatMessage[];
  choices: string[];
  /** 마지막 질문이 연 고용24 불러오기 목록 (2-0.4) */
  importKind?: ImportKind | null;
  sessionId?: string;
  /** 불러오기 목록을 받을 계정 */
  personaId?: string;
  onImport?: (importIds: string[]) => void;
  inputText: string;
  onInputChange: (text: string) => void;
  onChoice: (choice: string) => void;
  onSend: (text: string) => void;
  onFileSelect?: (file: File) => void;
  /** 지금 질문이 서류·사진을 요청했는지 (2-0.4 accepts_file) */
  isFileRequested?: boolean;
  isStreaming?: boolean;
  isUploading?: boolean;
  statusText?: string | null;
}

export const ChatPanel = ({
  messages,
  choices,
  importKind,
  sessionId,
  personaId,
  onImport,
  inputText,
  onInputChange,
  onChoice,
  onSend,
  onFileSelect,
  isFileRequested = false,
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
      id="dashboard-chat"
      aria-label="대화"
      className="flex h-[70dvh] w-full flex-col overflow-hidden lg:h-auto lg:min-h-0"
    >
      <div
        ref={logRef}
        className="scrollbar-hidden flex min-h-0 flex-1 flex-col gap-4 overflow-y-auto px-6 py-5 lg:px-8"
        role="log"
        aria-live="polite"
      >
        {messages.map((message) => (
          <MessageBubble key={message.id} message={message} />
        ))}
        {statusText && (
          <p role="status" className="flex items-center gap-2 text-sm font-semibold">
            <Sparkles
              aria-hidden
              size={ICON_SIZE.sm}
              strokeWidth={ICON_STROKE}
              className="text-ai-via motion-safe:animate-pulse"
            />
            <span className="text-ai-shimmer">{statusText}</span>
          </p>
        )}
        <ChoiceButtons choices={choices} onSelect={onChoice} isDisabled={isStreaming} />
        {importKind && sessionId && personaId && onImport && (
          <ImportPicker
            key={`${importKind}-${messages.length}`}
            kind={importKind}
            sessionId={sessionId}
            personaId={personaId}
            isDisabled={isStreaming}
            onApply={onImport}
          />
        )}
      </div>
      <ChatInput
        value={inputText}
        onChange={onInputChange}
        onSend={onSend}
        onFileSelect={onFileSelect}
        isFileRequested={isFileRequested}
        isDisabled={isStreaming}
        isUploading={isUploading}
      />
    </section>
  );
};

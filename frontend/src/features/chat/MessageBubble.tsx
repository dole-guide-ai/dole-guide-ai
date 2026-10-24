import Image from 'next/image';

import { Paperclip } from 'lucide-react';

import { EvidenceLine } from '@/components/EvidenceLine';
import type { ChatMessage } from '@/features/chat/chat.types';
import { CHAT_ROLE } from '@/features/chat/chat.types';

import { ICON_SIZE, ICON_STROKE } from '@/lib/iconSize';
import { INPUT_KIND } from '@/types/chat.types';

interface MessageBubbleProps {
  message: ChatMessage;
}

export const MessageBubble = ({ message }: MessageBubbleProps) => {
  if (message.role === CHAT_ROLE.SYSTEM) {
    return (
      <p
        role="alert"
        className="bg-danger-soft text-danger self-center rounded-xl px-4 py-2 text-center text-sm"
      >
        {message.text}
      </p>
    );
  }

  const isUser = message.role === CHAT_ROLE.USER;

  const bubble = (
    <div className={`flex min-w-0 flex-1 flex-col gap-1 ${isUser ? 'items-end' : 'items-start'}`}>
      {isUser && message.inputKind === INPUT_KIND.VOICE && (
        <span className="text-muted text-xs">음성 입력</span>
      )}
      {message.attachments?.map((attachment) => (
        <span
          key={attachment.name}
          className="border-line bg-surface text-ink inline-flex items-center gap-1.5 rounded-lg border px-3 py-1 text-sm"
        >
          <Paperclip aria-hidden size={ICON_SIZE.sm} strokeWidth={ICON_STROKE} />
          {attachment.name} · 읽기 요청
        </span>
      ))}
      <div
        className={`max-w-[85%] rounded-2xl px-4 py-3 text-base leading-relaxed whitespace-pre-line ${
          isUser ? 'bg-brand rounded-br-md text-white' : 'bg-neutral-soft text-ink rounded-bl-md'
        }`}
      >
        {message.text}
      </div>
      {!isUser && message.cite && <EvidenceLine cite={message.cite} />}
    </div>
  );

  if (isUser) return bubble;

  // AI 말풍선 옆에는 길잡이 아바타를 둡니다 (꾸밈 이미지라 alt는 비움).
  return (
    <div className="flex items-start gap-2">
      <Image
        src="/brand/avatar.svg"
        alt=""
        width={36}
        height={36}
        unoptimized
        className="mt-1 shrink-0"
      />
      {bubble}
    </div>
  );
};

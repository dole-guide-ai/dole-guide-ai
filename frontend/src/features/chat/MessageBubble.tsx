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

  const attachments = message.attachments?.map((attachment) => (
    <span
      key={attachment.name}
      className="border-line bg-surface text-ink inline-flex items-center gap-1.5 rounded-lg border px-3 py-1 text-sm"
    >
      <Paperclip aria-hidden size={ICON_SIZE.sm} strokeWidth={ICON_STROKE} />
      {attachment.name} · 읽기 요청
    </span>
  ));

  // 내 말: 오른쪽 옅은 회색 말풍선.
  if (isUser) {
    return (
      <div className="flex flex-col items-end gap-1">
        {message.inputKind === INPUT_KIND.VOICE && (
          <span className="text-muted text-xs">음성 입력</span>
        )}
        {attachments}
        <p className="bg-neutral-soft text-ink max-w-[85%] rounded-2xl px-4 py-3 text-base leading-relaxed whitespace-pre-line">
          {message.text}
        </p>
      </div>
    );
  }

  // 길잡이 말: 말풍선 없이 이름 줄(아바타·이름) 아래에 글을 그대로 둡니다 (꾸밈 이미지라 alt는 비움).
  return (
    <article className="flex flex-col gap-2" aria-label="길잡이 답변">
      <div className="flex items-center gap-2">
        <Image src="/brand/avatar.svg" alt="" width={26} height={26} unoptimized />
        <span className="text-muted text-sm font-semibold">실업급여 길잡이</span>
      </div>
      {attachments}
      <p className="text-ink text-base leading-relaxed whitespace-pre-line">{message.text}</p>
      {message.cite && <EvidenceLine cite={message.cite} />}
    </article>
  );
};

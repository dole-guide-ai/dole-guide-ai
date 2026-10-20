import { EvidenceLine } from '@/components/EvidenceLine';
import type { ChatMessage } from '@/features/chat/chat.types';

interface MessageBubbleProps {
  message: ChatMessage;
}

export const MessageBubble = ({ message }: MessageBubbleProps) => {
  if (message.role === 'system') {
    return (
      <p
        role="alert"
        className="bg-danger-soft text-danger self-center rounded-xl px-4 py-2 text-center text-sm"
      >
        {message.text}
      </p>
    );
  }

  const isUser = message.role === 'user';

  return (
    <div className={`flex flex-col gap-1 ${isUser ? 'items-end' : 'items-start'}`}>
      {isUser && message.inputKind === 'voice' && (
        <span className="text-muted text-xs">음성 입력</span>
      )}
      {message.attachments?.map((attachment) => (
        <span
          key={attachment.name}
          className="border-line bg-surface text-ink rounded-lg border px-3 py-1 text-sm"
        >
          📎 {attachment.name} · 읽기 요청
        </span>
      ))}
      <div
        className={`max-w-[85%] rounded-2xl px-4 py-3 text-base leading-relaxed whitespace-pre-line ${
          isUser
            ? 'bg-brand rounded-br-md text-white'
            : 'border-line bg-surface text-ink rounded-bl-md border shadow-xs'
        }`}
      >
        {message.text}
      </div>
      {!isUser && message.cite && <EvidenceLine cite={message.cite} />}
    </div>
  );
};

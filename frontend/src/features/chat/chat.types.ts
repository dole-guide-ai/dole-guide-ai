import type { ChatInputKind } from '@/types/chat.types';

export type ChatRole = 'assistant' | 'user' | 'system';

export interface ChatAttachment {
  name: string;
}

export interface ChatMessage {
  id: string;
  role: ChatRole;
  text: string;
  /** 근거 줄 (2-0.8). 규칙·절차를 말한 말풍선에만 있습니다. */
  cite?: string;
  inputKind?: ChatInputKind;
  /** 올린 파일 카드 (2-0.4). 이름만 두고 원본은 보관하지 않습니다. */
  attachments?: ChatAttachment[];
}

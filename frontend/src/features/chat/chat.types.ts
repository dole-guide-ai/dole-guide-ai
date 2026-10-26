import type { ChatInputKind, CiteLink } from '@/types/chat.types';

export const CHAT_ROLE = {
  ASSISTANT: 'assistant',
  USER: 'user',
  SYSTEM: 'system',
} as const;

export type ChatRole = (typeof CHAT_ROLE)[keyof typeof CHAT_ROLE];

export interface ChatAttachment {
  name: string;
}

export interface ChatMessage {
  id: string;
  role: ChatRole;
  text: string;
  /** 근거 줄 (2-0.8). 규칙·절차를 말한 말풍선에만 있습니다. */
  cite?: string;
  /** 근거 줄 원문 링크 (RAG 검색 자료) */
  citeLinks?: CiteLink[];
  inputKind?: ChatInputKind;
  /** 올린 파일 카드 (2-0.4). 이름만 두고 원본은 보관하지 않습니다. */
  attachments?: ChatAttachment[];
}

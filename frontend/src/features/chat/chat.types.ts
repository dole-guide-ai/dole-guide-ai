import type { ChatInputKind } from '@/types/chat.types';

export type ChatRole = 'assistant' | 'user' | 'system';

export interface ChatMessage {
  id: string;
  role: ChatRole;
  text: string;
  /** 근거 줄 (2-0.8). 규칙·절차를 말한 말풍선에만 있습니다. */
  cite?: string;
  inputKind?: ChatInputKind;
}

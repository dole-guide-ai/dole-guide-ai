import type { ChatState } from '@/features/chat/chatReducer';

import { type FormDrafts, getFormDrafts, replaceFormDraft } from '@/lib/formStore';

/**
 * 모의 화면의 새로고침 복원 (F-03). 실제 서버 화면은 `GET /accounts/{id}/messages`와 계정 조회로 되살리지만,
 * 모의 화면은 서버가 없으므로 대화와 패널 값을 이 탭의 sessionStorage에 잠깐 둡니다(모의 서버 저장소 역할).
 * 탭을 닫거나 `계정 바꾸기`·다시 입장하면 지웁니다. localStorage에는 두지 않습니다.
 */
const STORAGE_KEY = 'dole-guide.mock-state';

interface MockState {
  sessionId: string;
  chat?: ChatState;
  drafts?: FormDrafts;
}

const read = (): MockState | null => {
  if (typeof window === 'undefined') return null;
  try {
    const raw = window.sessionStorage.getItem(STORAGE_KEY);
    return raw ? (JSON.parse(raw) as MockState) : null;
  } catch {
    return null;
  }
};

const write = (state: MockState) => {
  if (typeof window === 'undefined') return;
  try {
    window.sessionStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  } catch {
    // 저장소를 못 쓰는 환경(시크릿 창 등)에서는 새로고침 복원만 빠집니다.
  }
};

const forSession = (sessionId: string): MockState => {
  const saved = read();
  return saved?.sessionId === sessionId ? saved : { sessionId };
};

export const saveMockChat = (sessionId: string, chat: ChatState) => {
  // 답이 흘러나오는 중인 말풍선 표시는 남기지 않습니다.
  write({ ...forSession(sessionId), chat: { ...chat, streamingId: null } });
};

export const loadMockChat = (sessionId: string): ChatState | null => {
  return forSession(sessionId).chat ?? null;
};

export const saveMockDrafts = (sessionId: string) => {
  write({ ...forSession(sessionId), drafts: getFormDrafts() });
};

/** 저장해 둔 패널 값을 양식 저장소로 되돌립니다. 되돌렸으면 true. */
export const restoreMockDrafts = (sessionId: string): boolean => {
  const drafts = forSession(sessionId).drafts;
  if (!drafts) return false;
  (Object.keys(drafts) as (keyof FormDrafts)[]).forEach((kind) =>
    replaceFormDraft(kind, drafts[kind]),
  );
  return true;
};

/** 되살린 패널 값이 있으면 모의 응답이 시드 대신 그 값을 돌려주도록 씁니다. */
export const hasRestoredValues = (values: Record<string, unknown>) =>
  Object.keys(values).length > 0;

export const clearMockState = () => {
  if (typeof window === 'undefined') return;
  try {
    window.sessionStorage.removeItem(STORAGE_KEY);
  } catch {
    // 지울 저장소가 없으면 그대로 둡니다.
  }
};

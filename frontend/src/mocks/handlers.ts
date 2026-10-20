import { ApiError } from '@/lib/api';
import { getSession } from '@/lib/sessionStore';
import type { DemoAuthCreate, PersonaCardRead, SessionRead } from '@/types/demo.types';

import { MOCK_AFTER_RESUME_ENTRIES, MOCK_ENTRIES } from './entries';
import { findMockPersona, MOCK_PERSONAS } from './personas';
import { MOCK_RESUMES } from './resumes';

/**
 * `NEXT_PUBLIC_USE_MOCK=1`일 때 `apiFetch`가 쓰는 모의 응답.
 * 경로·응답 형태는 상세기획 1.11 · 2-0.11을 따릅니다. 업무 로직은 두지 않고 스냅샷만 돌려줍니다.
 */
const MOCK_DELAY_MS = 150;

let authenticatedPersonaId: string | null = null;

const wait = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

const parseBody = <T>(init?: RequestInit): T | undefined => {
  if (!init?.body || typeof init.body !== 'string') return undefined;
  return JSON.parse(init.body) as T;
};

export const buildMockSession = (personaId: string): SessionRead => {
  const persona = findMockPersona(personaId);
  const entry = MOCK_ENTRIES[personaId];
  if (!persona || !entry) throw new ApiError('NOT_FOUND', `알 수 없는 계정: ${personaId}`, 404);
  return {
    session_id: `mock-${personaId}-${Date.now()}`,
    persona_id: personaId,
    state: persona.state,
    derived: persona.derived,
    entry,
  };
};

/** 테스트에서 인증 상태를 초기화할 때 씁니다. */
export const resetMockAuth = () => {
  authenticatedPersonaId = null;
};

export const resolveMock = async <T>(path: string, init?: RequestInit): Promise<T> => {
  const method = (init?.method ?? 'GET').toUpperCase();
  await wait(MOCK_DELAY_MS);

  if (method === 'GET' && path === '/health') {
    return { status: 'ok', db: 'mock' } as T;
  }

  if (method === 'GET' && path === '/auth/demo') {
    const cards: PersonaCardRead[] = MOCK_PERSONAS.map(({ persona_id, display }) => ({
      persona_id,
      display,
    }));
    return cards as T;
  }

  if (method === 'POST' && path === '/auth/demo') {
    const body = parseBody<DemoAuthCreate>(init);
    const persona = body ? findMockPersona(body.persona_id) : undefined;
    if (!persona) throw new ApiError('NOT_FOUND', '알 수 없는 계정이에요.', 404);
    authenticatedPersonaId = persona.persona_id;
    return { persona_id: persona.persona_id, display: persona.display } as T;
  }

  if (method === 'POST' && path === '/sessions') {
    if (!authenticatedPersonaId)
      throw new ApiError('UNAUTHORIZED', '먼저 계정을 골라 주세요.', 401);
    return buildMockSession(authenticatedPersonaId) as T;
  }

  // 새로 고침 뒤에는 모듈 상태가 비므로, 저장된 세션의 계정으로 이어 갑니다 (모의 전용).
  const personaId = authenticatedPersonaId ?? getSession()?.persona_id ?? null;

  if (method === 'GET' && path === '/forms/resume') {
    const resume = personaId ? MOCK_RESUMES[personaId] : undefined;
    if (!resume) throw new ApiError('NOT_FOUND', '이력서 초안이 없어요.', 404);
    return resume as T;
  }

  if (method === 'POST' && path === '/forms/resume/confirm') {
    const entry = personaId ? MOCK_AFTER_RESUME_ENTRIES[personaId] : undefined;
    if (!personaId || !entry) throw new ApiError('NOT_FOUND', '저장할 이력서가 없어요.', 404);
    const session = buildMockSession(personaId);
    return {
      ...session,
      state: { ...session.state, resume_status: 'ready', stage: 'education' },
      entry,
    } as T;
  }

  throw new ApiError('NOT_FOUND', `모의 응답이 없는 경로: ${method} ${path}`, 404);
};

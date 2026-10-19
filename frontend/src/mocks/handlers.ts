import { ApiError } from '@/lib/apiError';
import type { DemoAuthCreate, PersonaCardRead, SessionRead } from '@/types/demo.types';

import { MOCK_ENTRIES } from './entries';
import { findMockPersona, MOCK_PERSONAS } from './personas';

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
  if (!persona || !entry) throw new ApiError(404, '/sessions', `알 수 없는 계정: ${personaId}`);
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
    if (!persona) throw new ApiError(404, path, '알 수 없는 계정이에요.');
    authenticatedPersonaId = persona.persona_id;
    return { persona_id: persona.persona_id, display: persona.display } as T;
  }

  if (method === 'POST' && path === '/sessions') {
    if (!authenticatedPersonaId) throw new ApiError(401, path, '먼저 계정을 골라 주세요.');
    return buildMockSession(authenticatedPersonaId) as T;
  }

  throw new ApiError(404, path, `모의 응답이 없는 경로: ${method} ${path}`);
};

import { ApiError } from '@/lib/api';
import { getFormDrafts } from '@/lib/formStore';
import { getSession } from '@/lib/sessionStore';
import type { FormPatchCreate, FormUpdateEvent } from '@/types/chat.types';
import type { DemoAuthCreate, PersonaCardRead, SessionRead } from '@/types/demo.types';
import type { ImportKind } from '@/types/imports.types';
import type { MyDataDelete, MyDataRead } from '@/types/myData.types';
import type { ProcedurePatchCreate } from '@/types/procedure.types';
import type { RecognitionConfirmCreate } from '@/types/recognition.types';

import {
  MOCK_ACTIVITY_REMOVALS,
  MOCK_NEXT_ROUND_CHECKS,
  MOCK_PLANNED_ACTIVITIES,
  MOCK_RECOMMENDATIONS,
  MOCK_ROUND_CHECKS,
} from './activities';
import { resetMockChat } from './chatScripts';
import { MOCK_AFTER_RESUME_ENTRIES, MOCK_ENTRIES } from './entries';
import { MOCK_IMPORTS, mockImportList } from './imports';
import { MOCK_MY_DATA, MOCK_MY_DATA_DELETE_UPDATES, MOCK_NOT_STORED } from './myData';
import { findMockPersona, MOCK_PERSONAS } from './personas';
import { mockRecognitionForm } from './recognition';
import { MOCK_RESUMES } from './resumes';

/**
 * `NEXT_PUBLIC_USE_MOCK=1`일 때 `apiFetch`가 쓰는 모의 응답.
 * 경로·응답 형태는 상세기획 1.11 · 2-0.11을 따릅니다. 업무 로직은 두지 않고 스냅샷만 돌려줍니다.
 */
const MOCK_DELAY_MS = 150;

let authenticatedPersonaId: string | null = null;
/** 내 정보에서 지운 줄 (계정을 다시 고르면 seed로 초기화, 1.4) */
const deletedMyData = new Set<string>();

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
  resetMockChat();
  deletedMyData.clear();
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
    deletedMyData.clear();
    resetMockChat();
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

  if (
    method === 'POST' &&
    path === '/forms/resume/confirm' &&
    getSession()?.state.resume_status === 'ready'
  ) {
    // 이미 저장한 이력서를 고쳐 다시 저장: 이력서 ID·단계는 그대로이고 확정 스냅샷만 새로 남깁니다.
    return getSession() as T;
  }

  if (method === 'POST' && path === '/forms/resume/confirm') {
    const entry = personaId ? MOCK_AFTER_RESUME_ENTRIES[personaId] : undefined;
    if (!personaId || !entry) throw new ApiError('NOT_FOUND', '저장할 이력서가 없어요.', 404);
    const session = buildMockSession(personaId);
    return {
      ...session,
      // 같은 대화 세션이라 ID를 유지합니다. 바뀌면 닫은 주의 토스트가 다시 뜹니다 (시연 검증 4번).
      session_id: getSession()?.session_id ?? session.session_id,
      state: { ...session.state, resume_status: 'ready', stage: 'education' },
      entry,
    } as T;
  }

  if (method === 'POST' && path === '/files') {
    if (!(init?.body instanceof FormData) || !init.body.get('file')) {
      throw new ApiError('VALIDATION_ERROR', '파일이 없어요.', 422);
    }
    const stamp = Date.now();
    return { file_id: `file-${stamp}`, job_id: `job-${stamp}` } as T;
  }

  if (method === 'GET' && path === '/procedure/current-round/check') {
    const round = getSession()?.derived.current_round;
    const check = personaId
      ? ((round ? MOCK_NEXT_ROUND_CHECKS[personaId]?.[round] : undefined) ??
        MOCK_ROUND_CHECKS[personaId])
      : undefined;
    if (!check) throw new ApiError('NOT_FOUND', '이번 회차 정보가 없어요.', 404);
    return check as T;
  }

  if (method === 'GET' && path === '/procedure/current-round/recommendations') {
    const recommendations = personaId ? MOCK_RECOMMENDATIONS[personaId] : undefined;
    if (!recommendations) throw new ApiError('NOT_FOUND', '추천할 활동이 없어요.', 404);
    return recommendations as T;
  }

  const importMatch = /^\/imports\/(career-certificate|work24-activities)$/.exec(path);
  if (method === 'GET' && importMatch) {
    const list = personaId ? MOCK_IMPORTS[importMatch[1] as ImportKind][personaId] : undefined;
    if (!list) return { items: [], source_note: '불러올 내역이 없어요.' } as T;
    const drafts = getFormDrafts();
    return mockImportList(list, drafts.resume.values, drafts.activities.values) as T;
  }

  if (method === 'GET' && path === '/me/data') {
    const items = (personaId ? MOCK_MY_DATA[personaId] : undefined) ?? [];
    const read: MyDataRead = {
      items: items.filter((item) => !deletedMyData.has(item.item_id)),
      not_stored: MOCK_NOT_STORED,
    };
    return read as T;
  }

  if (method === 'DELETE' && path === '/me/data') {
    const body = parseBody<MyDataDelete>(init);
    const item = personaId
      ? MOCK_MY_DATA[personaId]?.find((row) => row.item_id === body?.item_id)
      : undefined;
    if (!item || deletedMyData.has(item.item_id)) {
      throw new ApiError('NOT_FOUND', '지울 정보를 찾지 못했어요.', 404);
    }
    if (!item.is_deletable) throw new ApiError('CONFLICT', '이 정보는 지울 수 없어요.', 409);
    deletedMyData.add(item.item_id);
    return { updates: MOCK_MY_DATA_DELETE_UPDATES[item.item_id] ?? [] } as T;
  }

  if (method === 'GET' && path === '/forms/recognition') {
    const form = personaId
      ? mockRecognitionForm(personaId, getFormDrafts().activities.values)
      : undefined;
    if (!form) throw new ApiError('NOT_FOUND', '실업인정 신청서 초안이 없어요.', 404);
    return form as T;
  }

  if (method === 'POST' && path === '/forms/recognition/confirm') {
    const body = parseBody<RecognitionConfirmCreate>(init);
    const form = personaId
      ? mockRecognitionForm(personaId, getFormDrafts().activities.values)
      : undefined;
    if (!form || !body || body.submit_mode !== form.submit_mode) {
      throw new ApiError('CONFLICT', '지금은 이 방법으로 낼 수 없어요.', 409);
    }
    // 실제 제출이 아니므로 `submitted`로 바꾸지 않고 `mock_submission`에만 적습니다 (2-3.7).
    return {
      ...form,
      status: 'finalized',
      mock_submission: body.submit_mode === 'attend' ? 'attend_ready' : 'sent',
    } as T;
  }

  if (method === 'PATCH' && path === '/procedure') {
    const body = parseBody<ProcedurePatchCreate>(init);
    if (body?.op === 'remove' && body.path.startsWith('activities.')) {
      const itemId = body.path.slice('activities.'.length);
      const removed: FormUpdateEvent = { form: 'activities', path: body.path, op: 'remove' };
      return { updates: [removed, ...(MOCK_ACTIVITY_REMOVALS[itemId] ?? [])] } as T;
    }
    const recommendationId = (body?.value as { recommendation_id?: string } | undefined)
      ?.recommendation_id;
    const planned = recommendationId ? MOCK_PLANNED_ACTIVITIES[recommendationId] : undefined;
    if (body?.path !== 'activities' || body.op !== 'append' || !planned) {
      throw new ApiError('VALIDATION_ERROR', '바꿀 내용을 알 수 없어요.', 422);
    }
    const update: FormUpdateEvent = {
      form: 'activities',
      path: 'activities',
      op: 'append',
      value: { item_id: `planned_${recommendationId}`, ...planned },
    };
    return { updates: [update] } as T;
  }

  if (method === 'PATCH' && path === '/forms/resume') {
    const body = parseBody<FormPatchCreate>(init);
    if (!body?.path) throw new ApiError('VALIDATION_ERROR', '고칠 칸을 알 수 없어요.', 422);
    const updates = [mockPatchUpdate(body)];
    // 저장한 이력서를 고치면 `draft`로 돌아가고 `다시 저장하기`로 재확정합니다 (2-1.6).
    if (personaId && MOCK_RESUMES[personaId]?.status === 'finalized') {
      updates.push(
        { form: 'resume', path: 'status', op: 'set', value: 'draft' },
        { form: 'resume', path: 'can_save', op: 'set', value: true },
      );
    }
    return { updates } as T;
  }

  throw new ApiError('NOT_FOUND', `모의 응답이 없는 경로: ${method} ${path}`, 404);
};

const YEAR_MONTH = /^\d{4}-(0[1-9]|1[0-2])$/;
const YEAR_MONTH_DAY = /^\d{4}-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])$/;
const MANUAL = { status: 'confirmed', source: 'manual' } as const;

/** 직접 입력 값 정리 흉내 (2-1.4): 날짜 칸은 연-월 형식만 받고, 그 밖에는 `직접 입력`으로 확정합니다. */
const mockPatchUpdate = (body: FormPatchCreate): FormUpdateEvent => {
  const value = typeof body.value === 'string' ? body.value.trim() : body.value;
  if (body.op === 'remove') return { form: 'resume', path: body.path, op: 'remove' };
  if (value === '' || value === undefined) {
    throw new ApiError('VALIDATION_ERROR', '값을 적어 주세요.', 422);
  }
  if (/acquired_date$/.test(body.path) && typeof value === 'string') {
    // 자격 취득일은 고용24 칸이 연-월-일입니다 (2-1.4).
    const normalized = value.replaceAll('.', '-');
    if (!YEAR_MONTH_DAY.test(normalized)) {
      throw new ApiError(
        'VALIDATION_ERROR',
        '취득일은 2011-05-20처럼 연-월-일로 적어 주세요.',
        422,
      );
    }
    return { form: 'resume', path: body.path, op: 'set', value: normalized, ...MANUAL };
  }
  if (/(start|end)_date$/.test(body.path) && typeof value === 'string') {
    const normalized = value.replaceAll('.', '-').replace(/-(\d)$/, '-0$1');
    if (!YEAR_MONTH.test(normalized)) {
      throw new ApiError('VALIDATION_ERROR', '날짜는 2004-03처럼 연-월로 적어 주세요.', 422);
    }
    return {
      form: 'resume',
      path: body.path,
      op: 'set',
      value: normalized,
      status: 'confirmed',
      source: 'manual',
    };
  }
  return {
    form: 'resume',
    path: body.path,
    op: 'set',
    value,
    status: 'confirmed',
    source: 'manual',
  };
};

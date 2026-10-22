import { ApiError } from '@/lib/api';
import { getFormDrafts } from '@/lib/formStore';
import { getSession, setSession } from '@/lib/sessionStore';
import type { components } from '@/types/api.gen';
import type { FormPatchCreate, FormUpdateEvent } from '@/types/chat.types';
import type { SessionRead } from '@/types/demo.types';
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
import { mockProcedureUpdates, resetMockChat } from './chatScripts';
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

type AccountRead = components['schemas']['AccountRead'];

/** 모의 계정 입장 응답. 화면은 `sessionFromAccount`로 세션을 만듭니다. */
export const mockAccount = (personaId: string): AccountRead => {
  const { state, derived, entry } = buildMockSession(personaId);
  const round = derived.current_round;
  return {
    persona_id: personaId,
    today: state.demo_today,
    procedure: {
      stage: state.stage,
      recipient_group: state.recipient_type === 'repeat' ? 'repeat' : derived.rule_group,
      age_at_separation: state.age_at_separation,
      has_disability: state.has_disability,
      separation_date: state.separation_date,
      education_done: state.education_done,
      eligibility_applied_on: state.eligibility_applied_date,
      first_recognition_date: null,
      benefit_days: 270,
      period_end_date: state.separation_date,
    },
    current_round:
      round && derived.period && state.next_recognition_date
        ? {
            round,
            period_start: derived.period.start,
            period_end: derived.period.end,
            recognition_date: state.next_recognition_date,
            attendance_required: derived.is_attendance_round,
            status: 'current',
            application_status: 'draft',
          }
        : null,
    entry: { ...entry, panel: entry.panel ?? 'A', flags: { m1: false } },
    pending_ask: null,
  };
};

/** 테스트에서 인증 상태를 초기화할 때 씁니다. */
export const resetMockAuth = () => {
  authenticatedPersonaId = null;
  resetMockChat();
  deletedMyData.clear();
};

/** 계정에 들어갈 때 mock 대화·삭제 상태를 비우고 입장 계정을 정합니다. 혼합 모드 입장에서도 씁니다. */
export const enterMockAccount = (personaId: string) => {
  authenticatedPersonaId = personaId;
  deletedMyData.clear();
  resetMockChat();
};

/** 절차 사실을 넣을 수 있는 단계 (백엔드 `services/procedure.py`와 같음, F-16). */
const PROCEDURE_STAGE: Record<string, string[]> = {
  '/education_done': ['job_registration', 'education'],
  '/eligibility_applied_on': ['eligibility_application'],
  '/first_recognition_date': ['eligibility_applied'],
};

type JsonPatchOp = components['schemas']['JsonPatchOp'];

const DAY_MS = 86_400_000;
const WAITING_DAYS = 7;
const ISO_DATE = /^\d{4}-\d{2}-\d{2}$/;

const invalid = (message = '바꿀 수 없는 칸이에요.') =>
  new ApiError('VALIDATION_ERROR', message, 422);

/** 달력에 있는 날짜(YYYY-MM-DD)인지 봅니다. */
const isCalendarDate = (value: unknown): value is string =>
  typeof value === 'string' &&
  ISO_DATE.test(value) &&
  new Date(`${value}T00:00:00Z`).toISOString().slice(0, 10) === value;

const addDays = (date: string, days: number) =>
  new Date(Date.parse(date) + days * DAY_MS).toISOString().slice(0, 10);

/** 토·일이면 다음 월요일, 아니면 그날. */
const nextWeekday = (date: string) => {
  const day = new Date(`${date}T00:00:00Z`).getUTCDay();
  return day === 6 ? addDays(date, 2) : day === 0 ? addDays(date, 1) : date;
};

/** 한 연산이 백엔드(`services/procedure.py`)와 같은 조건을 지키는지 봅니다. 어기면 422·409. */
const checkProcedureOp = (op: JsonPatchOp, { state, derived }: SessionRead) => {
  if (op.op === 'remove') throw invalid();
  const allowed = PROCEDURE_STAGE[op.path];
  if (!allowed) throw invalid();
  if (!allowed.includes(state.stage)) {
    throw new ApiError('STAGE_ORDER', '앞 단계를 먼저 마쳐야 해요.', 409);
  }
  if (op.path === '/education_done') {
    if (op.value !== true) throw invalid();
    if (state.resume_status !== 'ready') {
      throw new ApiError('STAGE_ORDER', '이력서를 먼저 저장해 주세요.', 409);
    }
    return;
  }
  if (!isCalendarDate(op.value)) throw invalid('날짜를 YYYY-MM-DD로 보내 주세요.');
  if (op.path === '/eligibility_applied_on') {
    if (!(state.separation_date < op.value && op.value <= state.demo_today)) {
      throw invalid('신청일은 그만둔 다음 날부터 오늘까지만 넣을 수 있어요.');
    }
    return;
  }
  const applied = state.eligibility_applied_date;
  if (!applied || op.value <= addDays(applied, WAITING_DAYS)) {
    throw invalid('1차 실업인정일은 신청일부터 7일 대기기간이 지난 뒤의 날짜예요.');
  }
  // 백엔드처럼 주말이면 다음 평일로 옮긴 날이 수급 종료 예정일 안이어야 합니다(모의는 공휴일을 따지지 않음).
  const end = derived.expected_end_date;
  if (end && nextWeekday(op.value) > end) {
    throw invalid('1차 실업인정일은 수급 종료 예정일 안의 날짜예요.');
  }
};

/**
 * 모의 `PATCH /accounts/{id}/procedure` (F-16). 백엔드와 같이 연산을 순서대로 검사·처리하고,
 * 앞 연산이 바꾼 상태를 다음 연산에 넘깁니다(교육 이수 + 신청일을 한 번에 보내도 둘 다 남음).
 * 하나라도 틀리면 아무것도 바꾸지 않고, 세션 저장소는 화면이 응답을 적용할 때 바뀝니다.
 */
const mockProcedurePatch = (ops: JsonPatchOp[]): FormUpdateEvent[] => {
  const original = getSession();
  if (!original || !ops.length) throw invalid();
  const updates: FormUpdateEvent[] = [];
  try {
    for (const op of ops) {
      const current = getSession() ?? original;
      checkProcedureOp(op, current);
      const opUpdates = mockProcedureUpdates(op.path, op.value);
      if (!opUpdates.length) throw invalid();
      // 다음 연산의 대본이 이 연산 뒤 상태에서 이어지도록 상태·파생값을 잠시 세션에 둡니다.
      const value = (path: string) => opUpdates.find((update) => update.path === path)?.value;
      setSession({
        ...current,
        state: (value('state') as SessionRead['state'] | undefined) ?? current.state,
        derived: (value('derived') as SessionRead['derived'] | undefined) ?? current.derived,
      });
      updates.push(...opUpdates);
    }
  } finally {
    setSession(original);
  }
  return updates;
};

export const resolveMock = async <T>(path: string, init?: RequestInit): Promise<T> => {
  const method = (init?.method ?? 'GET').toUpperCase();
  await wait(MOCK_DELAY_MS);

  if (method === 'GET' && path === '/health') {
    return { status: 'ok', db: 'mock' } as T;
  }

  if (method === 'GET' && path === '/personas') {
    const items = MOCK_PERSONAS.map(({ persona_id, display }) => ({
      persona_id,
      display,
      progress_summary: null,
    }));
    return { items, total: items.length } as T;
  }

  const accountMatch = /^\/accounts\/([a-z0-9_-]+)$/.exec(path);
  if (method === 'PUT' && accountMatch) {
    const account = mockAccount(accountMatch[1]);
    enterMockAccount(account.persona_id);
    return account as T;
  }

  if (method === 'PATCH' && /^\/accounts\/[a-z0-9_-]+\/procedure$/.test(path)) {
    const updates = mockProcedurePatch(parseBody<JsonPatchOp[]>(init) ?? []);
    // 단계가 바뀌었으니 직전 질문은 잊고, 다음 자유 입력은 새 단계 첫 질문에 답한 것으로 봅니다.
    resetMockChat();
    return { updates } as T;
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
    // 단계가 온라인 교육으로 바뀌므로 이력서 단계의 직전 질문은 잊습니다 (모의 자유 입력이 새 단계 첫 질문에 답하게).
    resetMockChat();
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

import { appendPath, removePath, setPath } from '@/lib/objectPath';
import { ROUND_CHECK_PATH, roundCheckFromServer } from '@/lib/roundCheck';
import type { components } from '@/types/api.gen';
import type {
  Completeness,
  FieldEvidence,
  FieldSource,
  FieldStatus,
  FormKind,
  FormUpdateEvent,
} from '@/types/chat.types';

type RoundCheck = components['schemas']['RoundCheck'];

/**
 * 패널 양식 초안을 모아 두는 외부 저장소. `form_update` 이벤트(2-0.7)를 경로대로 적용하고,
 * 패널 A·B·C는 여기서 값과 칸 상태(칩)를 읽습니다. 절차 상태(`procedure`)는 세션 저장소가 맡습니다.
 */
export interface FieldMeta {
  status: FieldStatus;
  source?: FieldSource;
  transformed?: boolean;
  evidence?: FieldEvidence;
}

export interface FormDraft {
  values: Record<string, unknown>;
  fields: Record<string, FieldMeta>;
  completeness?: Completeness;
}

export type FormDrafts = Record<FormKind, FormDraft>;

const emptyDraft = (): FormDraft => ({ values: {}, fields: {} });

const emptyDrafts = (): FormDrafts => ({
  resume: emptyDraft(),
  activities: emptyDraft(),
  recognition: emptyDraft(),
  procedure: emptyDraft(),
});

let drafts: FormDrafts = emptyDrafts();
const listeners = new Set<() => void>();

const emit = () => listeners.forEach((listener) => listener());

export const getFormDrafts = () => drafts;

export const subscribeForms = (listener: () => void) => {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
};

export const resetForms = () => {
  drafts = emptyDrafts();
  emit();
};

/** 서버에서 받은 초안 전체(GET /forms/{kind})로 바꿉니다. */
export const replaceFormDraft = (form: FormKind, draft: FormDraft) => {
  drafts = { ...drafts, [form]: draft };
  emit();
};

const LIST_END = '-';

/**
 * 백엔드의 JSON Pointer 경로·JSON Patch 연산(`/careers/-` add, `/hope_wage` replace)을
 * 저장소의 점 경로·연산(`careers` append, `hope_wage` set)으로 바꿉니다. 점 경로는 그대로 둡니다.
 */
export const toStoreUpdate = (
  path: string,
  op: FormUpdateEvent['op'],
): { path: string; op: 'set' | 'append' | 'remove' } => {
  if (!path.startsWith('/')) {
    return { path, op: op === 'add' ? 'append' : op === 'replace' ? 'set' : op };
  }
  const parts = path.slice(1).split('/');
  const appends = op === 'add' && parts.at(-1) === LIST_END;
  if (appends) parts.pop();
  const storeOp = op === 'remove' ? 'remove' : appends || op === 'append' ? 'append' : 'set';
  return { path: parts.join('.'), op: storeOp };
};

export const applyFormUpdateToDraft = (draft: FormDraft, event: FormUpdateEvent): FormDraft => {
  const { value } = event;
  const { path, op } = toStoreUpdate(event.path, event.op);
  let values = draft.values;
  const fields = { ...draft.fields };

  // `set`에 값이 없으면 값은 두고 칸 상태(칩)만 바꿉니다 (예: 확인 질문에 "네" → confirmed).
  if (op === 'set') {
    if (value !== undefined) values = setPath(values, path, value);
  } else if (op === 'append') values = appendPath(values, path, value);
  else {
    values = removePath(values, path);
    delete fields[path];
  }

  if (op !== 'remove' && event.status) {
    fields[path] = {
      status: event.status,
      source: event.source,
      transformed: event.transformed,
      evidence: event.evidence,
    };
  }

  return { values, fields, completeness: event.completeness ?? draft.completeness };
};

/** 쓰기 응답 `{updates}`의 바뀐 칸을 모두 적용합니다. */
export const applyFormUpdates = ({ updates }: { updates: FormUpdateEvent[] }) =>
  updates.forEach(applyFormUpdate);

export const applyFormUpdate = (event: FormUpdateEvent) => {
  if (event.form === 'activities' && event.path.startsWith('/')) {
    applyRoundCheckUpdate(event);
    return;
  }
  drafts = { ...drafts, [event.form]: applyFormUpdateToDraft(drafts[event.form], event) };
  emit();
};

/**
 * 백엔드의 패널 B 갱신 (F-17·F-20): 활동을 넣거나 빼면 `/round_check`로 다시 계산한 점검 전체가 옵니다.
 * 활동 한 건 경로(`/activities/{id}`)는 같은 응답의 점검 결과에 이미 들어 있어 따로 적용하지 않습니다.
 */
const applyRoundCheckUpdate = (event: FormUpdateEvent) => {
  if (event.path !== ROUND_CHECK_PATH || !event.value) return;
  const check = roundCheckFromServer(event.value as RoundCheck);
  // 추천 상자를 펼친 상태(대화가 보낸 화면 값)는 점검 결과가 아니라 그대로 둡니다.
  const { recommendations_open } = drafts.activities.values as { recommendations_open?: boolean };
  drafts = {
    ...drafts,
    activities: { values: { ...check, recommendations_open }, fields: {} },
  };
  emit();
};

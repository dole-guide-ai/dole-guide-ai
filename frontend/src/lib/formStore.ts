import { appendPath, removePath, setPath } from '@/lib/objectPath';
import type {
  Completeness,
  FieldEvidence,
  FieldSource,
  FieldStatus,
  FormKind,
  FormUpdateEvent,
} from '@/types/chat.types';

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

export const applyFormUpdateToDraft = (draft: FormDraft, event: FormUpdateEvent): FormDraft => {
  const { path, op, value } = event;
  let values = draft.values;
  const fields = { ...draft.fields };

  if (op === 'set') values = setPath(values, path, value);
  else if (op === 'append') values = appendPath(values, path, value);
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

export const applyFormUpdate = (event: FormUpdateEvent) => {
  drafts = { ...drafts, [event.form]: applyFormUpdateToDraft(drafts[event.form], event) };
  emit();
};

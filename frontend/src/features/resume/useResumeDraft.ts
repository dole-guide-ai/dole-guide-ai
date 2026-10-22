import { useSyncExternalStore } from 'react';

import { type FieldMeta, getFormDrafts, subscribeForms } from '@/lib/formStore';
import type { ResumeDraftRead } from '@/types/resume.types';

const selectResume = () => getFormDrafts().resume;

export type ResumeDraftValues = Partial<Omit<ResumeDraftRead, 'field_states' | 'completeness'>>;

/** 양식 저장소의 이력서 초안. 대화의 `form_update`가 들어올 때마다 다시 그려집니다. */
export const useResumeDraft = () => {
  const draft = useSyncExternalStore(subscribeForms, selectResume, selectResume);
  return {
    values: draft.values as ResumeDraftValues,
    fields: draft.fields as Record<string, FieldMeta>,
    completeness: draft.completeness,
  };
};

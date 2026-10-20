import { useSyncExternalStore } from 'react';

import { type FieldMeta, getFormDrafts, subscribeForms } from '@/lib/formStore';
import type { RecognitionFormRead } from '@/types/recognition.types';

const selectRecognition = () => getFormDrafts().recognition;

export type RecognitionDraftValues = Partial<Omit<RecognitionFormRead, 'field_states'>>;

/** 양식 저장소의 신청서 초안. 대화의 `form_update`가 들어올 때마다 다시 그려집니다. */
export const useRecognitionDraft = () => {
  const draft = useSyncExternalStore(subscribeForms, selectRecognition, selectRecognition);
  return {
    values: draft.values as RecognitionDraftValues,
    fields: draft.fields as Record<string, FieldMeta>,
  };
};

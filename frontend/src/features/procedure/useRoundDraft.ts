import { useSyncExternalStore } from 'react';

import { getFormDrafts, subscribeForms } from '@/lib/formStore';
import type { RoundCheckRead } from '@/types/procedure.types';

const selectActivities = () => getFormDrafts().activities;

/** 양식 저장소의 이번 회차 점검 결과. 대화의 `form_update`가 들어올 때마다 다시 그려집니다. */
export const useRoundDraft = () => {
  const draft = useSyncExternalStore(subscribeForms, selectActivities, selectActivities);
  return draft.values as Partial<RoundCheckRead>;
};

import { useEffect } from 'react';

import { useQuery } from '@tanstack/react-query';

import { apiFetch } from '@/lib/api';
import { API_PATHS } from '@/lib/apiPaths';
import { type FormDraft, replaceFormDraft } from '@/lib/formStore';
import { STALE_TIME } from '@/lib/queryConfig';
import { queryKeys } from '@/lib/queryKeys';
import type { RecognitionFormRead } from '@/types/recognition.types';

/** 서버 초안(2-3.10 JSON)을 양식 저장소 형태로 바꿉니다. `field_states`는 칸 상태, 나머지는 값입니다. */
export const toRecognitionDraft = (read: RecognitionFormRead): FormDraft => {
  const { field_states, ...values } = read;
  return { values, fields: field_states };
};

/**
 * `GET /forms/recognition`을 한 번 받아 양식 저장소 `recognition`에 넣습니다.
 * 본인 답변 같은 변화는 대화의 `form_update`가 맡고, 회차가 바뀌면 새로 받습니다.
 */
export const useRecognitionForm = (sessionId: string, round: number | null) => {
  const query = useQuery({
    queryKey: queryKeys.recognitionForm(sessionId, round),
    queryFn: () => apiFetch<RecognitionFormRead>(API_PATHS.LEGACY_RECOGNITION),
    staleTime: STALE_TIME.UNTIL_UPDATED,
    refetchOnWindowFocus: false,
  });

  useEffect(() => {
    if (query.data) replaceFormDraft('recognition', toRecognitionDraft(query.data));
  }, [query.data]);

  return query;
};

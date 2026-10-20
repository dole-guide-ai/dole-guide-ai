import { useEffect } from 'react';

import { useQuery } from '@tanstack/react-query';

import { apiFetch } from '@/lib/api';
import { replaceFormDraft } from '@/lib/formStore';
import { queryKeys } from '@/lib/queryKeys';
import type { RoundCheckRead } from '@/types/procedure.types';

/**
 * `GET /procedure/current-round/check`(2-2.6 `check_round` 결과)를 한 번 받아 양식 저장소 `activities`에 넣습니다.
 * 활동을 기록하면 대화의 `form_update`(form: "activities")가 저장소를 바꾸므로 다시 받아 덮어쓰지 않습니다.
 */
export const useRoundCheck = (sessionId: string) => {
  const query = useQuery({
    queryKey: queryKeys.roundCheck(sessionId),
    queryFn: () => apiFetch<RoundCheckRead>('/procedure/current-round/check'),
    staleTime: Infinity,
    refetchOnWindowFocus: false,
  });

  useEffect(() => {
    if (query.data) replaceFormDraft('activities', { values: { ...query.data }, fields: {} });
  }, [query.data]);

  return query;
};

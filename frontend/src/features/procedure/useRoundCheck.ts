import { useEffect } from 'react';

import { useQuery } from '@tanstack/react-query';

import { apiFetch } from '@/lib/api';
import { API_PATHS } from '@/lib/apiPaths';
import { replaceFormDraft } from '@/lib/formStore';
import { STALE_TIME } from '@/lib/queryConfig';
import { queryKeys } from '@/lib/queryKeys';
import { roundCheckFromServer } from '@/lib/roundCheck';
import type { components } from '@/types/api.gen';

type RoundCheck = components['schemas']['RoundCheck'];

/**
 * 지금 회차 점검 `GET /accounts/{id}/rounds/current` (F-18, `check_round` 결과)를 한 번 받아 양식 저장소
 * `activities`에 넣습니다. 활동을 넣거나 빼면 응답·대화의 `form_update`(`/round_check`)가 저장소를 바꾸므로
 * 다시 받아 덮어쓰지 않습니다.
 */
export const useRoundCheck = (sessionId: string, round: number | null, personaId: string) => {
  const query = useQuery({
    // 다음 회차로 넘어가면(2-3.7) 회차가 바뀌므로 새로 받습니다.
    queryKey: queryKeys.roundCheck(sessionId, round),
    queryFn: async () =>
      roundCheckFromServer(await apiFetch<RoundCheck>(API_PATHS.currentRound(personaId))),
    staleTime: STALE_TIME.UNTIL_UPDATED,
    refetchOnWindowFocus: false,
  });

  useEffect(() => {
    if (query.data) replaceFormDraft('activities', { values: { ...query.data }, fields: {} });
  }, [query.data]);

  return query;
};

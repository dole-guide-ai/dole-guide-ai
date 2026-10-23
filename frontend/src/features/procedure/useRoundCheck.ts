import { useEffect } from 'react';

import { useQuery } from '@tanstack/react-query';

import { isServerSession } from '@/lib/accountSession';
import { apiFetch } from '@/lib/api';
import { API_PATHS } from '@/lib/apiPaths';
import { replaceFormDraft } from '@/lib/formStore';
import { STALE_TIME } from '@/lib/queryConfig';
import { queryKeys } from '@/lib/queryKeys';
import { roundCheckFromServer } from '@/lib/roundCheck';
import type { components } from '@/types/api.gen';
import type { RoundCheckRead } from '@/types/procedure.types';

type RoundCheck = components['schemas']['RoundCheck'];

interface ServerAccount {
  personaId: string;
  ruleGroup: string;
}

/**
 * `GET /procedure/current-round/check`(2-2.6 `check_round` 결과)를 한 번 받아 양식 저장소 `activities`에 넣습니다.
 * 활동을 기록하면 대화의 `form_update`(form: "activities")가 저장소를 바꾸므로 다시 받아 덮어쓰지 않습니다.
 * 실제 서버 세션(`acct-`)이면 계정 회차 점검(`GET /accounts/{id}/rounds/current`)을 받아 같은 모양으로 바꿉니다 (F-22).
 */
export const useRoundCheck = (sessionId: string, round: number | null, account?: ServerAccount) => {
  const isServer = isServerSession(sessionId) && account !== undefined;
  const query = useQuery({
    // 다음 회차로 넘어가면(2-3.7) 회차가 바뀌므로 새로 받습니다.
    queryKey: queryKeys.roundCheck(sessionId, round),
    queryFn: async () =>
      isServer
        ? roundCheckFromServer(
            await apiFetch<RoundCheck>(API_PATHS.currentRound(account.personaId)),
            account.ruleGroup,
          )
        : apiFetch<RoundCheckRead>(API_PATHS.LEGACY_ROUND_CHECK),
    staleTime: STALE_TIME.UNTIL_UPDATED,
    refetchOnWindowFocus: false,
  });

  useEffect(() => {
    if (query.data) replaceFormDraft('activities', { values: { ...query.data }, fields: {} });
  }, [query.data]);

  return query;
};

import { useQuery } from '@tanstack/react-query';

import { isServerSession } from '@/lib/accountSession';
import { apiFetch } from '@/lib/api';
import { queryKeys } from '@/lib/queryKeys';
import { recommendationsFromServer } from '@/lib/recommendations';
import type { components } from '@/types/api.gen';
import type { RecommendationsRead } from '@/types/procedure.types';

type RecommendationList = components['schemas']['RecommendationList'];

/**
 * `GET /procedure/current-round/recommendations` (2-2.8). 추천 상자를 펼쳤을 때만 받습니다.
 * 실제 서버 세션(`acct-`)이면 `GET /accounts/{id}/rounds/current/recommendations`(F-19)를 씁니다.
 */
export const useRecommendations = (
  sessionId: string,
  enabled: boolean,
  personaId?: string,
  round?: number | null,
) =>
  useQuery({
    // 회차를 키에 넣어, 다음 회차로 넘어가면 그 회차 기준 추천을 새로 받습니다 (F-19).
    queryKey: queryKeys.roundRecommendations(sessionId, round),
    queryFn: async () =>
      isServerSession(sessionId) && personaId
        ? recommendationsFromServer(
            await apiFetch<RecommendationList>(
              `/accounts/${encodeURIComponent(personaId)}/rounds/current/recommendations`,
            ),
          )
        : apiFetch<RecommendationsRead>('/procedure/current-round/recommendations'),
    enabled,
    staleTime: Infinity,
  });

import { useQuery } from '@tanstack/react-query';

import { apiFetch } from '@/lib/api';
import { API_PATHS } from '@/lib/apiPaths';
import { STALE_TIME } from '@/lib/queryConfig';
import { queryKeys } from '@/lib/queryKeys';
import { recommendationsFromServer } from '@/lib/recommendations';
import type { components } from '@/types/api.gen';

type RecommendationList = components['schemas']['RecommendationList'];

/** `GET /accounts/{id}/rounds/current/recommendations` (F-19, 2-2.8). 추천 상자를 펼쳤을 때만 받습니다. */
export const useRecommendations = (
  sessionId: string,
  enabled: boolean,
  personaId: string,
  round?: number | null,
) =>
  useQuery({
    // 회차를 키에 넣어, 다음 회차로 넘어가면 그 회차 기준 추천을 새로 받습니다 (F-19).
    queryKey: queryKeys.roundRecommendations(sessionId, round),
    queryFn: async () =>
      recommendationsFromServer(
        await apiFetch<RecommendationList>(API_PATHS.recommendations(personaId)),
      ),
    enabled,
    staleTime: STALE_TIME.UNTIL_UPDATED,
  });

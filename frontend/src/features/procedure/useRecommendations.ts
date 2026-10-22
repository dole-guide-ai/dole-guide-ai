import { useQuery } from '@tanstack/react-query';

import { apiFetch } from '@/lib/api';
import { API_PATHS } from '@/lib/apiPaths';
import { STALE_TIME } from '@/lib/queryConfig';
import { queryKeys } from '@/lib/queryKeys';
import type { RecommendationsRead } from '@/types/procedure.types';

/** `GET /procedure/current-round/recommendations` (2-2.8). 추천 상자를 펼쳤을 때만 받습니다. */
export const useRecommendations = (sessionId: string, enabled: boolean) =>
  useQuery({
    queryKey: queryKeys.roundRecommendations(sessionId),
    queryFn: () => apiFetch<RecommendationsRead>(API_PATHS.LEGACY_ROUND_RECOMMENDATIONS),
    enabled,
    staleTime: STALE_TIME.UNTIL_UPDATED,
  });

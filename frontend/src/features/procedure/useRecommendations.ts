import { useQuery } from '@tanstack/react-query';

import { apiFetch } from '@/lib/api';
import { queryKeys } from '@/lib/queryKeys';
import type { RecommendationsRead } from '@/types/procedure.types';

/** `GET /procedure/current-round/recommendations` (2-2.8). 추천 상자를 펼쳤을 때만 받습니다. */
export const useRecommendations = (sessionId: string, enabled: boolean) =>
  useQuery({
    queryKey: queryKeys.roundRecommendations(sessionId),
    queryFn: () => apiFetch<RecommendationsRead>('/procedure/current-round/recommendations'),
    enabled,
    staleTime: Infinity,
  });

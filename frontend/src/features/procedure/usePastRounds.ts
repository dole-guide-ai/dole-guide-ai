import { useQuery } from '@tanstack/react-query';

import { apiFetch } from '@/lib/api';
import { queryKeys } from '@/lib/queryKeys';
import type { components } from '@/types/api.gen';

type RoundSummary = components['schemas']['RoundSummary'];
type ApplicationRead = components['schemas']['ApplicationRead'];

/** 지난 회차 목록 (`GET /accounts/{id}/rounds`에서 인정일이 지난 회차만, 최근 회차 먼저). F-04 */
export const usePastRounds = (personaId: string, enabled: boolean) =>
  useQuery({
    queryKey: queryKeys.rounds(personaId),
    queryFn: () =>
      apiFetch<{ items: RoundSummary[] }>(`/accounts/${encodeURIComponent(personaId)}/rounds`),
    select: (page) =>
      page.items.filter((round) => round.status === 'closed').sort((a, b) => b.round - a.round),
    enabled,
  });

/**
 * 지난 회차 신청서 한 장 (읽기 전용). 이번 회차 신청서처럼 양식 저장소에 넣지 않아,
 * 다시 봐도 지금 고치는 신청서가 바뀌지 않습니다.
 */
export const usePastApplication = (personaId: string, round: number) =>
  useQuery({
    queryKey: queryKeys.application(personaId, round),
    queryFn: () =>
      apiFetch<ApplicationRead>(
        `/accounts/${encodeURIComponent(personaId)}/rounds/${round}/application`,
      ),
    staleTime: Infinity,
  });

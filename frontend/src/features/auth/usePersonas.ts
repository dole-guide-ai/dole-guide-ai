import { useQuery } from '@tanstack/react-query';

import { apiFetch } from '@/lib/api';
import { API_PATHS } from '@/lib/apiPaths';
import { STALE_TIME } from '@/lib/queryConfig';
import { queryKeys } from '@/lib/queryKeys';
import type { components } from '@/types/api.gen';

export type PersonaCardRead = components['schemas']['PersonaCard'];
type PersonaList = components['schemas']['PersonaList'];

/** 로그인 카드 목록 (`GET /personas`). 이 방문자가 쓴 계정이면 진행 요약이 붙습니다. */
export const usePersonas = (enabled = true) =>
  useQuery({
    queryKey: queryKeys.personas,
    queryFn: () => apiFetch<PersonaList>(API_PATHS.personas),
    select: (data) => data.items,
    // 카드 목록은 자주 바뀌지 않아 화면을 옮겨 다녀도 다시 부르지 않습니다.
    staleTime: STALE_TIME.PERSONAS_MS,
    enabled,
  });

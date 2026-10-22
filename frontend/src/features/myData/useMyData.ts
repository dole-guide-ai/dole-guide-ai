import { useQuery } from '@tanstack/react-query';

import { apiFetch } from '@/lib/api';
import { API_PATHS } from '@/lib/apiPaths';
import { STALE_TIME } from '@/lib/queryConfig';
import { queryKeys } from '@/lib/queryKeys';
import type { MyDataRead } from '@/types/myData.types';

/** `GET /me/data` (2-0.9): 내 정보 창을 열 때마다 새로 받습니다. */
export const useMyData = (sessionId: string, enabled: boolean) =>
  useQuery({
    queryKey: queryKeys.myData(sessionId),
    queryFn: () => apiFetch<MyDataRead>(API_PATHS.LEGACY_MY_DATA),
    enabled,
    staleTime: STALE_TIME.ALWAYS_REFETCH,
  });

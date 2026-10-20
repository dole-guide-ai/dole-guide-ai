import { useQuery } from '@tanstack/react-query';

import { apiFetch } from '@/lib/api';
import { queryKeys } from '@/lib/queryKeys';
import type { MyDataRead } from '@/types/myData.types';

/** `GET /me/data` (2-0.9): 내 정보 창을 열 때마다 새로 받습니다. */
export const useMyData = (sessionId: string, enabled: boolean) =>
  useQuery({
    queryKey: queryKeys.myData(sessionId),
    queryFn: () => apiFetch<MyDataRead>('/me/data'),
    enabled,
    staleTime: 0,
  });

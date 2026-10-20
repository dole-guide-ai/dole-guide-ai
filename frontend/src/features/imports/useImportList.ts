import { useQuery } from '@tanstack/react-query';

import { apiFetch } from '@/lib/api';
import { queryKeys } from '@/lib/queryKeys';
import type { ImportKind, ImportListRead } from '@/types/imports.types';

/** `GET /imports/{kind}` (2-0.11 더한 경로): 고용24 불러오기 모의 목록. 열 때마다 새로 받습니다. */
export const useImportList = (kind: ImportKind, sessionId: string) =>
  useQuery({
    queryKey: queryKeys.imports(kind, sessionId),
    queryFn: () => apiFetch<ImportListRead>(`/imports/${kind}`),
    staleTime: 0,
  });

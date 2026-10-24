import { useQuery } from '@tanstack/react-query';

import { apiFetch } from '@/lib/api';
import { API_PATHS } from '@/lib/apiPaths';
import { STALE_TIME } from '@/lib/queryConfig';
import { queryKeys } from '@/lib/queryKeys';
import type { components } from '@/types/api.gen';
import type { ImportCategory, ImportKind, ImportListRead } from '@/types/imports.types';

type ImportList = components['schemas']['ImportList'];

/** 화면의 불러오기 종류 → 백엔드 경로 (설계 3.7) */
const IMPORT_PATH: Record<ImportKind, string> = {
  'career-certificate': 'career-certificates',
  'work24-activities': 'job-applications',
};

/** 백엔드 목록(`values`에 칸이 담김)을 불러오기 창 모양으로 바꿉니다. */
export const importsFromServer = (list: ImportList): ImportListRead => ({
  items: list.items.map((item) => ({
    import_id: item.import_id,
    category: item.values.category as ImportCategory,
    title: String(item.values.title ?? ''),
    detail: String(item.values.detail ?? ''),
    is_recorded: item.is_recorded,
  })),
  source_note: list.source_note,
});

/** `GET /accounts/{id}/imports/{kind}` (F-10): 고용24 불러오기 모의 목록. 열 때마다 새로 받습니다. */
export const useImportList = (kind: ImportKind, sessionId: string, personaId: string) =>
  useQuery({
    queryKey: queryKeys.imports(kind, sessionId),
    queryFn: async () =>
      importsFromServer(
        await apiFetch<ImportList>(API_PATHS.imports(personaId, IMPORT_PATH[kind])),
      ),
    staleTime: STALE_TIME.ALWAYS_REFETCH,
  });

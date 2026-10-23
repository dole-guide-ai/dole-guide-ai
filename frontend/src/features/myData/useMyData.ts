import { useQuery } from '@tanstack/react-query';

import { apiFetch } from '@/lib/api';
import { API_PATHS } from '@/lib/apiPaths';
import { STALE_TIME } from '@/lib/queryConfig';
import { queryKeys } from '@/lib/queryKeys';
import type { components } from '@/types/api.gen';
import type { MyDataRead } from '@/types/myData.types';

type FactList = components['schemas']['FactList'];

/** 백엔드 내 정보(`FactList`)를 내 정보 창 모양으로 바꿉니다. 줄 ID는 `fact_id`, 확인한 날은 `answered_on`. */
export const myDataFromFacts = (facts: FactList): MyDataRead => ({
  items: facts.items.map((fact) => ({
    item_id: fact.fact_id,
    group: fact.group,
    label: fact.label,
    value: fact.value ?? '',
    confirmed_on: fact.answered_on ?? null,
    is_deletable: fact.is_deletable,
  })),
  not_stored: facts.not_stored,
});

/** 내 정보 `GET /accounts/{id}/facts` (F-31, 2-0.9): 창을 열 때마다 새로 받습니다. */
export const useMyData = (sessionId: string, enabled: boolean, personaId: string) =>
  useQuery({
    queryKey: queryKeys.myData(sessionId),
    queryFn: async () => myDataFromFacts(await apiFetch<FactList>(API_PATHS.facts(personaId))),
    enabled,
    staleTime: STALE_TIME.ALWAYS_REFETCH,
  });

import { useEffect, useState } from 'react';

import { useQuery } from '@tanstack/react-query';

import { apiFetch } from '@/lib/api';
import { API_PATHS } from '@/lib/apiPaths';
import { STALE_TIME } from '@/lib/queryConfig';
import { queryKeys } from '@/lib/queryKeys';
import type { components } from '@/types/api.gen';

export type CodeRead = components['schemas']['CodeRead'];
type CodePage = components['schemas']['Page_CodeRead_'];

// 글자를 칠 때마다 부르지 않고 잠깐 멈췄을 때 찾습니다.
const SEARCH_DELAY_MS = 250;
// 드롭다운에 보일 후보 수 (GET /codes/{kind} limit 최대 20)
const SEARCH_LIMIT = 10;

/** 검색해서 고르는 공통코드 종류 → 검색 경로 (지역은 전체 목록을 두 단계로 고름) */
export const SEARCH_KIND = {
  occupation: 'occupations',
  license: 'licenses',
  major: 'majors',
} as const;
export type SearchKind = keyof typeof SEARCH_KIND;

/** 고용24 지역 코드 전체 (`GET /codes/regions`). 화면은 parent로 시·도 → 시·군·구를 만듭니다. */
export const useRegionCodes = () =>
  useQuery({
    queryKey: queryKeys.codeRegions,
    queryFn: () => apiFetch<CodePage>(API_PATHS.codeRegions),
    select: (data) => data.items,
    staleTime: STALE_TIME.CODES,
  });

/**
 * 공통코드 이름 검색 (`GET /codes/{occupations|licenses|majors}`). 찾는 기준은 대화와 같이 서버가
 * 정합니다. 코드표를 아직 받지 않은 종류는 빈 목록이 와서 "이름만 적기"만 남습니다.
 */
export const useCodeSearch = (kind: SearchKind, text: string) => {
  const [query, setQuery] = useState(text.trim());
  useEffect(() => {
    const timer = window.setTimeout(() => setQuery(text.trim()), SEARCH_DELAY_MS);
    return () => window.clearTimeout(timer);
  }, [text]);
  return useQuery({
    queryKey: queryKeys.codeSearch(kind, query),
    queryFn: () => apiFetch<CodePage>(API_PATHS.codeSearch(SEARCH_KIND[kind], query, SEARCH_LIMIT)),
    select: (data) => data.items,
    staleTime: STALE_TIME.CODES,
    enabled: query.length > 0,
  });
};

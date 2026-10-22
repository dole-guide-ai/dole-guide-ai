/** TanStack Query 캐시 시간(staleTime). 화면마다 숫자를 직접 쓰지 않고 여기 이름을 씁니다. */
export const STALE_TIME = {
  /** 쓰기 응답(form_update)으로 직접 갱신하는 서류·회차 데이터. 다시 불러오지 않습니다. */
  UNTIL_UPDATED: Infinity,
  /** 열 때마다 새로 불러오는 목록(내 정보·불러오기). */
  ALWAYS_REFETCH: 0,
  /** 거의 바뀌지 않는 계정 카드 목록. */
  PERSONAS_MS: 5 * 60_000,
} as const;

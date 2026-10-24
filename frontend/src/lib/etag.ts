/** 서류 PATCH 낙관적 잠금 헤더(백엔드 `If-Match`, 설계 3.11). 없으면 409 VERSION_CONFLICT입니다. */
export const IF_MATCH_HEADER = 'If-Match';

/** GET 응답의 `lock_version`을 ETag 모양(`"3"`)으로 만듭니다. */
export const ifMatch = (lockVersion: number | undefined) => `"${Number(lockVersion ?? 0)}"`;

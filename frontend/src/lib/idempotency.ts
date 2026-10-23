/** POST 재시도 중복 방지 헤더(백엔드 `Idempotency-Key`). 같은 키로 다시 보내면 한 번만 처리됩니다. */
export const IDEMPOTENCY_HEADER = 'Idempotency-Key';

/** 보낼 때마다 새 키를 만듭니다. */
export const newIdempotencyKey = () => crypto.randomUUID();

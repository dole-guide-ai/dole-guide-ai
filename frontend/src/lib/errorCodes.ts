import type { components } from '@/types/api.gen';

type ServerErrorCode = components['schemas']['ErrorCode'];

/**
 * 화면에서 분기하거나 직접 만드는 오류 코드. 서버 코드는 api.gen.ts의 ErrorCode와 같고,
 * `NETWORK_ERROR`만 서버에 닿지 못했을 때 프론트가 쓰는 코드입니다.
 */
export const ERROR_CODES = {
  NOT_FOUND: 'NOT_FOUND',
  CONFLICT: 'CONFLICT',
  VALIDATION_ERROR: 'VALIDATION_ERROR',
  FILE_TOO_LARGE: 'FILE_TOO_LARGE',
  TURN_IN_PROGRESS: 'TURN_IN_PROGRESS',
  RATE_LIMITED: 'RATE_LIMITED',
  LLM_UNAVAILABLE: 'LLM_UNAVAILABLE',
  TIMEOUT: 'TIMEOUT',
  INTERNAL_ERROR: 'INTERNAL_ERROR',
  NETWORK_ERROR: 'NETWORK_ERROR',
} as const satisfies Record<string, ServerErrorCode | 'NETWORK_ERROR'>;

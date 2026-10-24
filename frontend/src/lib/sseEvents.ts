/**
 * 대화 턴 SSE 이벤트 이름. 기준은 `shared/sse-events.json`이고, 이벤트별 타입을 나누려고
 * 같은 값을 리터럴 상수로 둡니다(`sseEvents.test.ts`가 두 곳이 같은지 확인).
 * 이벤트 이름은 문자열로 직접 쓰지 말고 여기 상수를 씁니다.
 */
export const SSE_EVENTS = {
  TOKEN: 'token',
  TOOL_CALL: 'tool_call',
  ASK_USER: 'ask_user',
  FORM_UPDATE: 'form_update',
  DONE: 'done',
  ERROR: 'error',
} as const;

export type SseEventName = (typeof SSE_EVENTS)[keyof typeof SSE_EVENTS];

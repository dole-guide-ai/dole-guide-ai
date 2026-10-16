import sseEvents from '../../../shared/sse-events.json';

export const SSE_EVENTS = sseEvents;

export type SseEventName = (typeof SSE_EVENTS)[keyof typeof SSE_EVENTS];

import { describe, expect, it } from 'vitest';

import { SSE_EVENTS } from '@/lib/sseEvents';

import sharedEvents from '../../../shared/sse-events.json';

describe('SSE_EVENTS', () => {
  it('shared/sse-events.json과 같다', () => {
    expect(SSE_EVENTS).toEqual(sharedEvents);
  });
});

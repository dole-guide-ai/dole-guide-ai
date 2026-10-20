import { describe, expect, it } from 'vitest';

import { parseSseBlock, parseSseStream } from '@/lib/sse';
import { sseResponse } from '@/test/mockSse';

describe('parseSseBlock', () => {
  it('event·data 줄을 읽고 주석과 빈 줄은 무시한다', () => {
    expect(parseSseBlock(': keep-alive\nevent: token\ndata: {"text":"안녕"}')).toEqual({
      event: 'token',
      data: '{"text":"안녕"}',
    });
  });

  it('data 줄이 여러 개면 줄바꿈으로 잇고, 이벤트 이름이 없으면 message다', () => {
    expect(parseSseBlock('data: a\ndata: b')).toEqual({ event: 'message', data: 'a\nb' });
  });

  it('data가 없으면 이벤트를 만들지 않는다', () => {
    expect(parseSseBlock('event: done')).toBeNull();
  });
});

describe('parseSseStream', () => {
  it('덩어리 경계가 이벤트 중간에 걸려도 이벤트 단위로 모은다', async () => {
    const res = sseResponse(
      [
        { event: 'token', data: { text: '이정호님,' } },
        { event: 'done', data: { cite: '출처' } },
      ],
      5,
    );

    const events = [];
    for await (const event of parseSseStream(res.body!)) events.push(event);

    expect(events).toEqual([
      { event: 'token', data: '{"text":"이정호님,"}' },
      { event: 'done', data: '{"cite":"출처"}' },
    ]);
  });

  it('CRLF 줄바꿈도 읽는다', async () => {
    const stream = new Response('event: token\r\ndata: {"text":"a"}\r\n\r\n').body!;

    const events = [];
    for await (const event of parseSseStream(stream)) events.push(event);

    expect(events).toEqual([{ event: 'token', data: '{"text":"a"}' }]);
  });
});

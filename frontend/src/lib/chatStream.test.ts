import { afterEach, describe, expect, it, vi } from 'vitest';

import { ApiError } from '@/lib/api';
import { streamChat } from '@/lib/chatStream';
import { sseResponse } from '@/test/mockSse';

afterEach(() => vi.unstubAllGlobals());

describe('streamChat', () => {
  it('계정의 messages 경로로 백엔드 본문 형식(text)을 보내고 이벤트를 읽는다', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      sseResponse([
        { event: 'token', data: { text: '안녕하세요' } },
        { event: 'done', data: {} },
      ]),
    );
    vi.stubGlobal('fetch', fetchMock);

    const stream = await streamChat('lee', 'acct-lee-2026-10-21', {
      message: '합성 질문',
      input_kind: 'text',
    });
    const events = [];
    for await (const event of stream) events.push(event);

    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe('/api/accounts/lee/messages');
    expect(JSON.parse(init.body)).toEqual({
      text: '합성 질문',
      input_kind: 'text',
      file_ids: [],
      import_ids: [],
    });
    expect(events.map((e) => e.event)).toEqual(['token', 'done']);
  });

  it('턴 진행 중(409)이면 코드를 담은 ApiError를 던진다', async () => {
    vi.stubGlobal(
      'fetch',
      vi
        .fn()
        .mockResolvedValue(
          Response.json(
            { code: 'TURN_IN_PROGRESS', message: '진행 중', details: null },
            { status: 409 },
          ),
        ),
    );

    await expect(
      streamChat('lee', 's', { message: '합성', input_kind: 'text' }),
    ).rejects.toMatchObject({ code: 'TURN_IN_PROGRESS', status: 409 });
    await expect(
      streamChat('lee', 's', { message: '합성', input_kind: 'text' }),
    ).rejects.toBeInstanceOf(ApiError);
  });
});

import { afterEach, describe, expect, it, vi } from 'vitest';

import { refreshAccount } from '@/lib/refreshAccount';
import { getSession, setSession } from '@/lib/sessionStore';
import { ACCOUNTS, sessionFor } from '@/test/fixtures';
import { mockFetchJson } from '@/test/mockFetch';

describe('refreshAccount', () => {
  afterEach(() => {
    vi.restoreAllMocks();
    setSession(null);
  });

  it('서버가 판정한 알림·마감·단계는 바꾸고 첫 안내는 그대로 둔다', async () => {
    const before = sessionFor('choi');
    setSession(before);
    // 최영수가 고용센터에서 수급자격을 신청해 단계가 넘어가면 서버는 방문 안내를 거둡니다.
    mockFetchJson({
      ...ACCOUNTS.choi,
      procedure: { ...ACCOUNTS.choi.procedure, stage: 'eligibility_applied' },
      notices: [],
      entry: { ...ACCOUNTS.choi.entry, title: '다른 첫 안내' },
    });

    await refreshAccount('choi');

    const after = getSession();
    expect(before.notices.map((n) => n.kind)).toEqual(['visit']);
    expect(after?.notices).toEqual([]);
    expect(after?.state.stage).toBe('eligibility_applied');
    expect(after?.entry).toEqual(before.entry);
  });

  it('다시 받기에 실패하면 지금 세션을 그대로 둔다', async () => {
    const before = sessionFor('lee');
    setSession(before);
    mockFetchJson({ code: 'INTERNAL', message: '오류', details: [] }, { status: 500 });

    await refreshAccount('lee');

    expect(getSession()).toEqual(before);
  });
});

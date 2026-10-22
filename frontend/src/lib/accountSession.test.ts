import { describe, expect, it } from 'vitest';

import { sessionFromAccount } from '@/lib/accountSession';
import type { components } from '@/types/api.gen';
import { resolveMock } from '@/mocks/handlers';

type AccountRead = components['schemas']['AccountRead'];

describe('sessionFromAccount', () => {
  it('새로고침 전 멈춘 질문이 있으면 그 선택지를 다시 띄운다 (F-03)', async () => {
    const account = await resolveMock<AccountRead>('/accounts/lee', { method: 'PUT' });

    const restored = sessionFromAccount({
      ...account,
      pending_ask: {
        question_id: 'activity.category',
        text: '어떤 활동이었어요?',
        choices: ['입사지원', '면접', '다른 활동'],
        import_kind: null,
      },
    });

    expect(restored.entry.choices).toEqual(['입사지원', '면접', '다른 활동']);
    expect(sessionFromAccount({ ...account, pending_ask: null }).entry.choices).toEqual(
      account.entry.choices,
    );
  });
});

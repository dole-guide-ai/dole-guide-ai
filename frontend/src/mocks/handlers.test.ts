import { beforeEach, describe, expect, it } from 'vitest';

import { ApiError } from '@/lib/api';
import type { PersonaCardRead, SessionRead } from '@/types/demo.types';
import { resetMockAuth, resolveMock } from '@/mocks/handlers';

describe('모의 API', () => {
  beforeEach(() => resetMockAuth());

  it('계정 목록은 카드 표시용 값만 돌려준다', async () => {
    const cards = await resolveMock<PersonaCardRead[]>('/auth/demo');

    expect(cards.map((card) => card.persona_id)).toEqual(['park', 'choi', 'lee']);
    expect(cards[0]).not.toHaveProperty('state');
  });

  it('계정을 고르기 전에는 세션을 만들 수 없다', async () => {
    await expect(resolveMock('/sessions', { method: 'POST' })).rejects.toBeInstanceOf(ApiError);
  });

  it('이정호를 고르면 E4b 진입 결과가 나온다', async () => {
    await resolveMock('/auth/demo', {
      method: 'POST',
      body: JSON.stringify({ persona_id: 'lee' }),
    });
    const session = await resolveMock<SessionRead>('/sessions', { method: 'POST' });

    expect(session.entry.branch_id).toBe('E4b');
    expect(session.entry.panel).toBe('B');
    expect(session.derived.d_day).toBe(6);
    expect(session.entry.choices).toHaveLength(3);
  });

  it('최영수는 글자 크게가 기본으로 켜진다 (M4)', async () => {
    await resolveMock('/auth/demo', {
      method: 'POST',
      body: JSON.stringify({ persona_id: 'choi' }),
    });
    const session = await resolveMock<SessionRead>('/sessions', { method: 'POST' });

    expect(session.entry.branch_id).toBe('E7b');
    expect(session.entry.ui.big_text).toBe(true);
  });
});

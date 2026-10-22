import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { RecommendationBox } from '@/features/procedure/RecommendationBox';

import { renderWithProviders } from '@/test/renderWithProviders';

const serverList = {
  items: [
    {
      recommendation_id: 'rec_4_work24_apply',
      category: 'job_search',
      kind: 'job_application',
      title: '입사지원 (고용24) — 희망 직종 ‘일반 사무’ 공고',
      reason: '구직활동 · 증빙 불필요',
      evidence_hint: null,
      external: { rule_refs: ['ACT-001', 'ACT-132'] },
    },
    {
      recommendation_id: 'rec_4_step_lecture',
      category: 'non_job_search',
      kind: 'lecture',
      title: '온라인 취업특강 (STEP) — 1과정 끝까지(진도율 100%)',
      reason: '구직 외 활동 · 증빙 불필요 · 한도 2회 중 0회 사용',
      evidence_hint: null,
      external: { rule_refs: ['ACT-043'] },
    },
  ],
  total: 2,
  deadline_text: '10.26(월)까지 해 두세요.',
  cite: null,
};

describe('RecommendationBox (F-19 실제 서버 세션)', () => {
  afterEach(() => vi.restoreAllMocks());

  it('계정 추천을 받아 보여 주고, 선택하면 추천 ID로 예정 활동을 넣는다', async () => {
    const fetchSpy = vi
      .spyOn(globalThis, 'fetch')
      .mockImplementation(async (_input, init) =>
        init?.method === 'POST'
          ? Response.json({ updates: [] }, { status: 201 })
          : Response.json(serverList),
      );
    renderWithProviders(
      <RecommendationBox sessionId="acct-lee-2026-10-21" plannedIds={[]} personaId="lee" />,
    );

    expect(await screen.findByText(/1\. 입사지원 \(고용24\)/)).toBeInTheDocument();
    expect(screen.getByText('한도 2회 중 0회 사용')).toBeInTheDocument();
    expect(screen.getByText('10.26(월)까지 해 두세요.')).toBeInTheDocument();
    expect(String(fetchSpy.mock.calls[0][0])).toContain(
      '/accounts/lee/rounds/current/recommendations',
    );

    await userEvent.click(screen.getByRole('button', { name: /입사지원 \(고용24\).* 선택/ }));

    const [url, init] = fetchSpy.mock.calls[1];
    expect(String(url)).toContain('/accounts/lee/activities');
    expect(init?.method).toBe('POST');
    expect(JSON.parse(String(init?.body))).toEqual({ recommendation_id: 'rec_4_work24_apply' });
    expect(await screen.findByRole('button', { name: /입사지원.* 선택/ })).toHaveTextContent(
      '선택함',
    );
  });
});

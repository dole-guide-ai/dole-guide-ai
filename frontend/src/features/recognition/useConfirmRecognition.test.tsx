import type { ReactNode } from 'react';

import { QueryClientProvider } from '@tanstack/react-query';
import { renderHook, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { useConfirmRecognition } from '@/features/recognition/useConfirmRecognition';

import { createTestQueryClient } from '@/test/renderWithProviders';

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });

const empty = { status: 'missing', transformed: false };
const application = {
  round: 4,
  status: 'submitted',
  lock_version: 2,
  period_start: '2026-11-25',
  period_end: '2026-12-22',
  recognition_date: '2026-12-22',
  attendance_required: true,
  required_activities: 2,
  required_job_search: 1,
  data: {
    work: { has_work: empty, entries: empty },
    employment: { status: empty, started_on: empty },
    industrial_accident: { receiving: empty },
    credit: {
      application: empty,
      notice_method: empty,
      auto_payment: empty,
      income_asset_consent: empty,
    },
    notification_method: empty,
    next_plan: empty,
    privacy_consent: empty,
  },
  job_search_rows: [],
  other_rows: [],
  excluded_rows: [],
  checklist: { blocking: [], warnings: [] },
  submit_mode: 'attend',
  can_submit: false,
};

const wrapper = ({ children }: { children: ReactNode }) => (
  <QueryClientProvider client={createTestQueryClient()}>{children}</QueryClientProvider>
);

describe('useConfirmRecognition (F-27)', () => {
  afterEach(() => vi.restoreAllMocks());

  it('실제 서버 세션은 회차 신청서 PATCH로 제출하고 준비물을 같이 보낸다', async () => {
    const fetchSpy = vi
      .spyOn(globalThis, 'fetch')
      .mockImplementation(async (input, init) =>
        init?.method === 'PATCH' ? json({ updates: [] }) : json(application),
      );
    const { result } = renderHook(() => useConfirmRecognition('acct-lee-2026-12-16', 'lee', 4), {
      wrapper,
    });

    result.current.mutate({ submit_mode: 'attend', attend_items: ['id_card', 'eligibility_card'] });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    const [url, init] = fetchSpy.mock.calls[0];
    expect(String(url)).toBe('/api/accounts/lee/rounds/4/application');
    expect(init?.method).toBe('PATCH');
    expect(JSON.parse(String(init?.body))).toEqual([
      { op: 'replace', path: '/status', value: 'submitted' },
      { op: 'replace', path: '/submit_mode', value: 'attend' },
      { op: 'replace', path: '/attend_items', value: ['id_card', 'eligibility_card'] },
    ]);
    expect(result.current.data?.status).toBe('finalized');
  });

  it('제출(PATCH)이 되면 다시 받기가 실패해도 성공으로 보고, 신청서 캐시를 갱신한다', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation(async (_input, init) =>
      init?.method === 'PATCH'
        ? json({ updates: [] })
        : json({ code: 'INTERNAL_ERROR', message: '잠시 뒤 다시 시도해 주세요.' }, 500),
    );
    const queryClient = createTestQueryClient();
    const key = ['forms', 'recognition', 'acct-lee-2026-12-16', 4];
    queryClient.setQueryData(key, { status: 'review', can_submit: true, mock_submission: null });
    const { result } = renderHook(() => useConfirmRecognition('acct-lee-2026-12-16', 'lee', 4), {
      wrapper: ({ children }: { children: ReactNode }) => (
        <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
      ),
    });

    result.current.mutate({ submit_mode: 'send' });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toBeNull();
    // 받아 둔 신청서를 제출 완료로 바꿔, 다시 받기 전에도 제출 버튼이 다시 열리지 않습니다
    expect(queryClient.getQueryData(key)).toMatchObject({
      status: 'finalized',
      can_submit: false,
      mock_submission: 'sent',
    });
    expect(queryClient.getQueryState(key)?.isInvalidated).toBe(true);
  });
});

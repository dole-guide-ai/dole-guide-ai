import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { PanelFrame } from '@/features/dashboard/PanelFrame';
import { PastRounds } from '@/features/procedure/PastRounds';

import { buildMockSession } from '@/mocks/handlers';
import { renderWithProviders } from '@/test/renderWithProviders';

const round = (no: number, status: 'closed' | 'current', applicationStatus = 'submitted') => ({
  round: no,
  period_start: '2026-11-25',
  period_end: '2026-12-22',
  recognition_date: no === 3 ? '2026-11-24' : '2026-12-22',
  attendance_required: false,
  status,
  application_status: applicationStatus,
});

const application = {
  round: 3,
  status: 'submitted',
  lock_version: 2,
  period_start: '2026-10-28',
  period_end: '2026-11-24',
  recognition_date: '2026-11-24',
  attendance_required: false,
  required_activities: 1,
  required_job_search: 0,
  data: {},
  job_search_rows: [
    {
      activity_id: 'a1',
      activity_date: '2026-11-10',
      company_name: 'OO물류',
      application_method: '고용24(워크넷)',
      file_ids: [],
    },
  ],
  other_rows: [],
  excluded_rows: [],
  checklist: { blocking: [], warnings: [] },
  submit_mode: 'change',
  can_submit: false,
};

const serverSession = () => ({ ...buildMockSession('lee'), session_id: 'acct-lee-2026-10-21' });

describe('PastRounds (F-04)', () => {
  afterEach(() => vi.restoreAllMocks());

  it('지난 회차만 최근 회차부터 보여 주고, 누르면 그 회차 신청서를 읽기 전용으로 연다', async () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
      const url = String(input);
      if (url.endsWith('/accounts/lee/rounds')) {
        return Response.json({
          items: [round(2, 'closed'), round(3, 'closed'), round(4, 'current', 'draft')],
          total: 3,
        });
      }
      return Response.json(application);
    });
    renderWithProviders(<PastRounds session={serverSession()} />);

    const buttons = await screen.findAllByRole('button', { name: /차 ·/ });
    expect(buttons.map((button) => button.textContent)).toEqual([
      '3차 · 11.24(화)제출함',
      '2차 · 12.22(화)제출함',
    ]);

    await userEvent.click(buttons[0]);
    expect(await screen.findByText(/OO물류/)).toBeInTheDocument();
    expect(String(fetchSpy.mock.calls.at(-1)?.[0])).toContain('/accounts/lee/rounds/3/application');
    expect(screen.queryByRole('button', { name: /모의/ })).toBeNull();
  });

  it('모의 세션에서는 보이지 않고 요청도 보내지 않는다', () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch');
    const { container } = renderWithProviders(<PastRounds session={buildMockSession('lee')} />);

    expect(container).toBeEmptyDOMElement();
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it('이번 회차가 없어도(모든 회차 종료) 패널 B에서 지난 회차를 볼 수 있다', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation(async () =>
      Response.json({ items: [round(3, 'closed')], total: 1 }),
    );
    const session = serverSession();
    renderWithProviders(
      <PanelFrame
        session={{
          ...session,
          state: { ...session.state, next_recognition_date: null },
          entry: { ...session.entry, panel: 'B' },
        }}
      />,
    );

    expect(await screen.findByRole('region', { name: '지난 회차 신청서' })).toBeInTheDocument();
  });
});

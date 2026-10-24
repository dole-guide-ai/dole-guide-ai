import { act, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { RoundPanel } from '@/features/procedure/RoundPanel';

import { applyFormUpdate, resetForms } from '@/lib/formStore';
import { ROUND_CHECK_PATH } from '@/lib/roundCheck';
import { sessionFor } from '@/test/fixtures';
import { renderWithProviders } from '@/test/renderWithProviders';
import {
  activityCheck,
  LEE_ROUND_CHECK,
  LEE_ROUND_CHECK_SATISFIED,
} from '@/test/roundCheckFixture';

const RECOMMENDATIONS = {
  items: [
    {
      recommendation_id: 'rec_4_work24_apply',
      category: 'job_search',
      kind: 'job_application',
      title: '입사지원 (고용24)',
      reason: '구직활동 · 증빙 불필요',
      evidence_hint: null,
      external: { rule_refs: ['ACT-001'] },
    },
    {
      recommendation_id: 'rec_4_step_lecture',
      category: 'non_job_search',
      kind: 'lecture',
      title: '온라인 취업특강 (STEP)',
      reason: '구직 외 활동 · 증빙 불필요 · 한도 2회 중 0회 사용',
      evidence_hint: null,
      external: { rule_refs: ['ACT-043'] },
    },
  ],
  total: 2,
  deadline_text: '12월 21일(월)까지 해 두세요.',
};

const roundCheckUpdate = (value: unknown) => ({
  form: 'activities' as const,
  path: ROUND_CHECK_PATH,
  op: 'replace' as const,
  value,
});

const mockApi = (options: { checkStatus?: number } = {}) =>
  vi.spyOn(globalThis, 'fetch').mockImplementation(async (input, init) => {
    const url = String(input);
    if (url.endsWith('/accounts/lee/rounds/current')) {
      return options.checkStatus
        ? Response.json(
            { code: 'INTERNAL_ERROR', message: '회차 점검을 못 했어요.' },
            { status: options.checkStatus },
          )
        : Response.json(LEE_ROUND_CHECK);
    }
    if (url.endsWith('/rounds/current/recommendations')) return Response.json(RECOMMENDATIONS);
    if (url.endsWith('/accounts/lee/activities/a2') && init?.method === 'DELETE') {
      // OO상사를 빼면 OO물류만 남고 같은 날 경고도 사라집니다 (F-20).
      return Response.json({
        updates: [
          { form: 'activities', path: '/activities/a2', op: 'remove' },
          roundCheckUpdate({
            ...LEE_ROUND_CHECK,
            activities: [LEE_ROUND_CHECK.activities[0]],
            warnings: [],
          }),
        ],
      });
    }
    if (url.endsWith('/accounts/lee/activities') && init?.method === 'POST') {
      const planned = activityCheck({
        activity_id: 'p1',
        activity_date: '2026-12-21',
        org_name: null,
        source: 'auto',
        planned: true,
        status: 'planned',
      });
      return Response.json(
        {
          updates: [
            { form: 'activities', path: '/activities/p1', op: 'add', value: planned },
            roundCheckUpdate({
              ...LEE_ROUND_CHECK,
              activities: [...LEE_ROUND_CHECK.activities, planned],
            }),
          ],
        },
        { status: 201 },
      );
    }
    return Response.json({ code: 'NOT_FOUND', message: '없는 경로예요.' }, { status: 404 });
  });

const session = () => sessionFor('lee');

describe('RoundPanel', () => {
  beforeEach(() => resetForms());
  afterEach(() => vi.restoreAllMocks());

  it('이정호 기록 전: 1건 더, 같은 날 계산 제외, W1 경고, D-day·회차 진행', async () => {
    mockApi();

    renderWithProviders(<RoundPanel session={session()} />);

    expect(await screen.findByLabelText('필요 활동 결과')).toHaveTextContent('인정 1건 · 1건 더');
    expect(screen.getByText('D-6')).toBeInTheDocument();
    expect(screen.getByText('같은 날 · 계산 제외')).toBeInTheDocument();
    expect(screen.getByText('12월 8일 활동은 2건이지만 하루 1건만 인정돼요.')).toBeInTheDocument();
    expect(screen.getAllByText('주의')).toHaveLength(2);
    const progress = screen.getByRole('list', { name: '회차 진행' });
    expect(within(progress).getByText('4차 ! (출석)')).toHaveAttribute('aria-current', 'step');
    expect(screen.getByText(/검수 전 규칙으로 계산했어요/)).toBeInTheDocument();
    expect(screen.queryByRole('region', { name: '추천 활동' })).not.toBeInTheDocument();
  });

  it('점검 결과를 못 받으면 서버 문구를 보여 주고, 신청서로는 넘어갈 수 있다 (F-22)', async () => {
    mockApi({ checkStatus: 500 });
    const onOpenForm = vi.fn();

    renderWithProviders(<RoundPanel session={session()} onOpenForm={onOpenForm} />);

    expect(await screen.findByRole('alert')).toHaveTextContent('회차 점검을 못 했어요.');
    await userEvent.click(screen.getByRole('button', { name: '활동 정리 끝 · 신청서 만들기' }));
    expect(onOpenForm).toHaveBeenCalledTimes(1);
  });

  it('추천 요청이 오면 추천 상자를 펼치고, 선택하면 예정 활동으로 들어간다', async () => {
    mockApi();
    renderWithProviders(<RoundPanel session={session()} />);
    await screen.findByLabelText('필요 활동 결과');

    act(() =>
      applyFormUpdate({
        form: 'activities',
        path: 'recommendations_open',
        op: 'set',
        value: true,
      }),
    );

    const box = await screen.findByRole('region', { name: '추천 활동' });
    expect(within(box).getByText('한도 2회 중 0회 사용')).toBeInTheDocument();
    await userEvent.click(within(box).getByRole('button', { name: '입사지원 (고용24) 선택' }));

    expect(await screen.findByText('예정')).toBeInTheDocument();
    expect(within(box).getByRole('button', { name: '입사지원 (고용24) 선택' })).toBeDisabled();
  });

  it('활동을 기록해 충족되면 카드가 충족으로 바뀐다', async () => {
    mockApi();
    renderWithProviders(<RoundPanel session={session()} />);
    await screen.findByLabelText('필요 활동 결과');

    act(() => applyFormUpdate(roundCheckUpdate(LEE_ROUND_CHECK_SATISFIED)));

    expect(screen.getByLabelText('필요 활동 결과')).toHaveTextContent('인정 2건 · 충족');
    expect(screen.getByText('OO물산')).toBeInTheDocument();
  });

  it('부족한 채로 신청서를 누르면 한 번 묻고, 그래도 보면 넘어간다', async () => {
    mockApi();
    const onOpenForm = vi.fn();
    renderWithProviders(<RoundPanel session={session()} onOpenForm={onOpenForm} />);

    await userEvent.click(
      await screen.findByRole('button', { name: '활동 정리 끝 · 신청서 만들기' }),
    );
    expect(screen.getByText('아직 1건 부족해요. 그래도 신청서를 볼까요?')).toBeInTheDocument();
    expect(onOpenForm).not.toHaveBeenCalled();

    await userEvent.click(screen.getByRole('button', { name: '그래도 볼게요' }));
    expect(onOpenForm).toHaveBeenCalledTimes(1);
  });

  it('충족이면 묻지 않고 바로 신청서로 넘어간다 (F-22)', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce(Response.json(LEE_ROUND_CHECK_SATISFIED));
    const onOpenForm = vi.fn();
    renderWithProviders(<RoundPanel session={session()} onOpenForm={onOpenForm} />);

    await userEvent.click(
      await screen.findByRole('button', { name: '활동 정리 끝 · 신청서 만들기' }),
    );
    expect(screen.queryByText(/건 부족해요/)).not.toBeInTheDocument();
    expect(onOpenForm).toHaveBeenCalledTimes(1);
  });

  it('활동 빼기는 한 번 묻고, 다시 계산한 결과로 목록·경고를 바꾼다 (2-2.11)', async () => {
    mockApi();
    renderWithProviders(<RoundPanel session={session()} />);

    await userEvent.click(await screen.findByRole('button', { name: 'OO상사 활동 빼기' }));
    expect(screen.getByText('이 활동을 목록에서 뺄까요? 다시 계산해요.')).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: '뺄게요' }));

    await vi.waitFor(() => expect(screen.queryByText('OO상사')).not.toBeInTheDocument());
    expect(screen.queryByRole('list', { name: '경고' })).not.toBeInTheDocument();
  });

  it('인정일이 지났으면 변경 신청 안내를 맨 위에 보여 준다 (E2)', async () => {
    mockApi();
    const lee = session();
    renderWithProviders(
      <RoundPanel session={{ ...lee, derived: { ...lee.derived, d_day: -2 } }} />,
    );

    expect(await screen.findByText(/실업인정일이 지났어요\./)).toBeInTheDocument();
    expect(screen.getByText(/14일 안에 고용센터에 가서 변경 신청/)).toBeInTheDocument();
  });
});

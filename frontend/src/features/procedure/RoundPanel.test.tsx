import { act, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { RoundPanel } from '@/features/procedure/RoundPanel';

import { applyFormUpdate, resetForms } from '@/lib/formStore';
import { MOCK_RECOMMENDATIONS, MOCK_ROUND_CHECKS } from '@/mocks/activities';
import { buildMockSession } from '@/mocks/handlers';
import { renderWithProviders } from '@/test/renderWithProviders';

const mockApi = (options: { checkStatus?: number } = {}) =>
  vi.spyOn(globalThis, 'fetch').mockImplementation(async (input, init) => {
    const url = String(input);
    if (url.endsWith('/procedure/current-round/check')) {
      return options.checkStatus
        ? Response.json(
            { code: 'INTERNAL_ERROR', message: '회차 점검을 못 했어요.' },
            { status: options.checkStatus },
          )
        : Response.json(MOCK_ROUND_CHECKS.lee);
    }
    if (url.endsWith('/procedure/current-round/recommendations')) {
      return Response.json(MOCK_RECOMMENDATIONS.lee);
    }
    if (url.endsWith('/procedure') && init?.method === 'PATCH') {
      return Response.json({
        updates: [
          {
            form: 'activities',
            path: 'activities',
            op: 'append',
            value: {
              ...MOCK_ROUND_CHECKS.lee.activities[0],
              item_id: 'planned_rec_work24_apply',
              date: '2026-12-18',
              org_name: '(공고 선택 전)',
              status: 'planned',
            },
          },
        ],
      });
    }
    return Response.json({ code: 'NOT_FOUND', message: '없는 경로예요.' }, { status: 404 });
  });

const session = () => buildMockSession('lee');

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

  it('점검 결과를 못 받으면 서버 문구를 보여 준다', async () => {
    mockApi({ checkStatus: 500 });

    renderWithProviders(<RoundPanel session={session()} />);

    expect(await screen.findByRole('alert')).toHaveTextContent('회차 점검을 못 했어요.');
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

    act(() => {
      applyFormUpdate({
        form: 'activities',
        path: 'activities',
        op: 'append',
        value: {
          ...MOCK_ROUND_CHECKS.lee.activities[0],
          item_id: 'a3',
          date: '2026-12-16',
          org_name: 'OO물산',
        },
      });
      applyFormUpdate({ form: 'activities', path: 'counted', op: 'set', value: 2 });
      applyFormUpdate({ form: 'activities', path: 'shortfall', op: 'set', value: 0 });
      applyFormUpdate({ form: 'activities', path: 'status', op: 'set', value: 'satisfied' });
    });

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
});

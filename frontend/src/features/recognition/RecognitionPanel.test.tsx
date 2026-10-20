import { act, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { RecognitionPanel } from '@/features/recognition/RecognitionPanel';

import { applyFormUpdate, resetForms } from '@/lib/formStore';
import type { RecognitionFormRead } from '@/types/recognition.types';
import { buildMockSession } from '@/mocks/handlers';
import { MOCK_RECOGNITION_FORMS } from '@/mocks/recognition';
import { renderWithProviders } from '@/test/renderWithProviders';

const mockApi = (form: RecognitionFormRead = MOCK_RECOGNITION_FORMS.lee) =>
  vi.spyOn(globalThis, 'fetch').mockImplementation(async (input, init) => {
    const url = String(input);
    if (url.endsWith('/forms/recognition')) return Response.json(form);
    if (url.endsWith('/forms/recognition/confirm') && init?.method === 'POST') {
      return Response.json({ ...form, status: 'finalized', mock_submission: 'attend_ready' });
    }
    return Response.json({ code: 'NOT_FOUND', message: '없는 경로예요.' }, { status: 404 });
  });

const SELF = { status: 'confirmed', source: 'self_answer' } as const;

const answerAll = () => {
  for (const key of [
    'has_work_or_service',
    'has_employment',
    'has_industrial_accident_benefit_right',
  ]) {
    applyFormUpdate({
      form: 'recognition',
      path: `work_and_employment.${key}`,
      op: 'set',
      value: false,
      ...SELF,
    });
  }
  applyFormUpdate({
    form: 'recognition',
    path: 'work_and_employment.answered_on',
    op: 'set',
    value: '2026-12-16',
  });
  applyFormUpdate({
    form: 'recognition',
    path: 'notification_and_plan.next_activity',
    op: 'set',
    value: { value: '구직활동', memo: '입사지원', answered_on: '2026-12-16' },
    ...SELF,
  });
  applyFormUpdate({
    form: 'recognition',
    path: 'checklist',
    op: 'set',
    value: MOCK_RECOGNITION_FORMS.lee.checklist.map((item) => ({ ...item, done: true })),
  });
  applyFormUpdate({ form: 'recognition', path: 'can_submit', op: 'set', value: true });
};

describe('RecognitionPanel', () => {
  beforeEach(() => resetForms());
  afterEach(() => vi.restoreAllMocks());

  it('이정호 4차 본인 답변 전 (시안 2-3-1): 답변 필요 4개, 지난 답, 구직활동 2건, 버튼 비활성', async () => {
    mockApi();

    renderWithProviders(<RecognitionPanel session={buildMockSession('lee')} />);

    // 근로·취업·산재 3개 + 다음 출석일까지 활동
    expect(await screen.findAllByText('답변 필요')).toHaveLength(4);
    expect(screen.getAllByText('본인 확인 · 11.24').length).toBeGreaterThan(0);
    expect(screen.getByText('11.25 ~ 12.22')).toBeInTheDocument();
    expect(screen.getByRole('article', { name: '구직활동 OO물류' })).toBeInTheDocument();
    expect(screen.getByRole('article', { name: '구직활동 OO물산' })).toBeInTheDocument();
    expect(screen.getByText(/계산에서 뺀 활동 1건/)).toBeInTheDocument();
    expect(screen.getByText(/OO상사 · 같은 날/)).toBeInTheDocument();
    // 고용24로 지원한 건은 증빙이 따로 필요 없어요 (ACT-132)
    expect(screen.getAllByText('증빙 불필요 (고용24 지원)')).toHaveLength(2);
    expect(screen.getByText(/출석 회차라 인터넷으로 내지 않아요/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '출석 준비 확인 (모의)' })).toBeDisabled();
    expect(
      screen.getByText(/남은 것: 근로·취업·산재 본인 답변, 다음 출석일까지 활동/),
    ).toBeInTheDocument();
  });

  it('본인 답변을 마치고 준비물을 체크하면 출석 준비 확인을 할 수 있다 (시안 2-3-2)', async () => {
    mockApi();
    const onConfirmed = vi.fn();
    renderWithProviders(
      <RecognitionPanel session={buildMockSession('lee')} onConfirmed={onConfirmed} />,
    );
    await screen.findAllByText('답변 필요');

    act(answerAll);

    expect(screen.queryByText('답변 필요')).not.toBeInTheDocument();
    expect(screen.getAllByText('본인 확인 · 12.16').length).toBeGreaterThan(0);
    const button = screen.getByRole('button', { name: '출석 준비 확인 (모의)' });
    expect(button).toBeDisabled();

    const box = screen.getByRole('region', { name: '제출 전 확인' });
    await userEvent.click(within(box).getByRole('checkbox', { name: '신분증' }));
    await userEvent.click(within(box).getByRole('checkbox', { name: '수급자격증' }));
    await userEvent.click(button);

    expect(await screen.findByRole('button', { name: '확인했어요 (모의)' })).toBeDisabled();
    expect(onConfirmed).toHaveBeenCalledWith('attend');
  });

  it('취업했다고 답하면 신청서 작성을 멈춘다', async () => {
    mockApi({ ...MOCK_RECOGNITION_FORMS.lee, locked_reason: 'employment' });

    renderWithProviders(<RecognitionPanel session={buildMockSession('lee')} />);

    expect(await screen.findByRole('alert')).toHaveTextContent('관할 고용센터에 먼저 문의');
    expect(screen.queryByRole('region', { name: '제출 전 확인' })).not.toBeInTheDocument();
  });

  it('활동이 부족하면 경고와 활동 다시 보기를 보여 준다', async () => {
    const lee = MOCK_RECOGNITION_FORMS.lee;
    mockApi({
      ...lee,
      reemployment_activity: {
        ...lee.reemployment_activity,
        counted: { activities: 1, job_search: 1 },
      },
    });
    const onBackToRound = vi.fn();

    renderWithProviders(
      <RecognitionPanel session={buildMockSession('lee')} onBackToRound={onBackToRound} />,
    );

    expect(await screen.findByText(/필요 활동이 1건 부족해요/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: '활동 다시 보기' }));
    expect(onBackToRound).toHaveBeenCalledTimes(1);
  });

  it('근로 있음이면 고용24 칸대로 상세 4칸을 보여 준다 (2-3.3)', async () => {
    const lee = MOCK_RECOGNITION_FORMS.lee;
    mockApi({
      ...lee,
      work_and_employment: {
        ...lee.work_and_employment,
        has_work_or_service: true,
        work_details: {
          work_dates: '2026-12-05 (1일)',
          total_hours: 8,
          income_date: null,
          income_amount: 100000,
        },
      },
    });

    renderWithProviders(<RecognitionPanel session={buildMockSession('lee')} />);

    expect(await screen.findByText('2026-12-05 (1일)')).toBeInTheDocument();
    expect(screen.getByText('8시간')).toBeInTheDocument();
    expect(screen.getByText('100,000원')).toBeInTheDocument();
    expect(screen.getByText('소득수령(예정)일')).toBeInTheDocument();
    expect(screen.getByText(/일한 날은 신청서에 꼭 적어야 해요/)).toBeInTheDocument();
  });

  it('구직 외 활동이 있으면 과정·세부내역 카드를 보여 준다 (2-3.2)', async () => {
    const lee = MOCK_RECOGNITION_FORMS.lee;
    mockApi({
      ...lee,
      reemployment_activity: {
        ...lee.reemployment_activity,
        has_other_reemployment_activity: true,
        other_reemployment_activities: [
          {
            item_id: 'other_001',
            course: '온라인 취업특강 프로그램',
            details: null,
            attachment_ids: [],
            source: 'conversation',
          },
        ],
      },
    });

    renderWithProviders(<RecognitionPanel session={buildMockSession('lee')} />);

    const card = await screen.findByRole('article', {
      name: '구직 외 활동 온라인 취업특강 프로그램',
    });
    expect(within(card).getByText('답변 필요')).toBeInTheDocument();
    // 대화로 더한 활동은 첨부가 없으면 증빙이 필요하다고 보여 줍니다
    expect(within(card).getByText('증빙 필요')).toBeInTheDocument();
    expect(screen.queryByText('구직활동 외 활동사항 · 없음')).not.toBeInTheDocument();
  });
});

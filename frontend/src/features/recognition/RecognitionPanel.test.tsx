import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { RecognitionPanel } from '@/features/recognition/RecognitionPanel';

import { resetForms } from '@/lib/formStore';
import type { components } from '@/types/api.gen';
import { LEE_APPLICATION, sessionFor } from '@/test/fixtures';
import { renderWithProviders } from '@/test/renderWithProviders';

type ApplicationRead = components['schemas']['ApplicationRead'];

/** 회차 신청서 가짜 서버: GET은 떠 둔 응답(이정호 4차), PATCH(제출)는 제출된 신청서를 돌려줍니다. */
const mockApi = (application: ApplicationRead = LEE_APPLICATION) =>
  vi.spyOn(globalThis, 'fetch').mockImplementation(async (input, init) => {
    const url = String(input);
    if (url.includes('/rounds/') && url.endsWith('/application')) {
      if (init?.method === 'PATCH') return Response.json({ updates: [] });
      return Response.json(application, { headers: { ETag: `"${application.lock_version}"` } });
    }
    return Response.json({ code: 'NOT_FOUND', message: '없는 경로예요.' }, { status: 404 });
  });

const field = (value: unknown) => ({ value, status: 'confirmed', source: 'user_answer' });

describe('RecognitionPanel (실제 신청서 API 응답)', () => {
  beforeEach(() => resetForms());
  afterEach(() => vi.restoreAllMocks());

  it('이정호 4차 본인 답변 전: 답변 필요, 인정 활동·같은 날 제외, 출석 회차, 버튼 비활성', async () => {
    mockApi();

    renderWithProviders(<RecognitionPanel session={sessionFor('lee')} />);

    expect((await screen.findAllByText('답변 필요')).length).toBeGreaterThanOrEqual(4);
    expect(screen.getByRole('article', { name: '구직활동 OO물류' })).toBeInTheDocument();
    expect(screen.getByText(/OO상사 · 같은 날/)).toBeInTheDocument();
    expect(screen.getByText(/출석 회차라 인터넷으로 내지 않아요/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '출석 준비 확인 (모의)' })).toBeDisabled();
    expect(screen.getByText(/남은 것: .*근로·취업·산재 본인 답변/)).toBeInTheDocument();
  });

  it('취업했다고 답하면 신청서 작성을 멈춘다', async () => {
    mockApi({ ...LEE_APPLICATION, locked_reason: 'employed' });

    renderWithProviders(<RecognitionPanel session={sessionFor('lee')} />);

    expect(await screen.findByRole('alert')).toHaveTextContent('관할 고용센터에 먼저 문의');
    expect(screen.queryByRole('region', { name: '제출 전 확인' })).not.toBeInTheDocument();
  });

  it('활동이 부족하면 경고와 활동 다시 보기를 보여 준다', async () => {
    mockApi();
    const onBackToRound = vi.fn();

    renderWithProviders(
      <RecognitionPanel session={sessionFor('lee')} onBackToRound={onBackToRound} />,
    );

    expect(await screen.findByText(/필요 활동이 1건 부족해요/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: '활동 다시 보기' }));
    expect(onBackToRound).toHaveBeenCalledTimes(1);
  });

  it('근로 있음이면 고용24 칸대로 상세 4칸을 보여 준다 (2-3.3)', async () => {
    const work = {
      has_work: field('yes'),
      entries: field([
        {
          item_id: 'w1',
          worked_on: '2026-10-05',
          hours: 8,
          income_received_on: null,
          amount: 100000,
        },
      ]),
    };
    mockApi({ ...LEE_APPLICATION, data: { ...LEE_APPLICATION.data, work } as never });

    renderWithProviders(<RecognitionPanel session={sessionFor('lee')} />);

    expect(await screen.findByText('8시간')).toBeInTheDocument();
    expect(screen.getByText('100,000원')).toBeInTheDocument();
    expect(screen.getByText('소득수령(예정)일')).toBeInTheDocument();
  });

  it('구직 외 활동이 있으면 과정·세부내역 카드를 보여 준다 (2-3.2)', async () => {
    mockApi({
      ...LEE_APPLICATION,
      other_rows: [
        { activity_id: 'o1', activity_date: '2026-10-14', kind: 'lecture', details: null },
      ],
    });

    renderWithProviders(<RecognitionPanel session={sessionFor('lee')} />);

    expect(await screen.findByRole('article', { name: /구직 외 활동/ })).toBeInTheDocument();
    expect(screen.queryByText('구직활동 외 활동사항 · 없음')).not.toBeInTheDocument();
  });
});

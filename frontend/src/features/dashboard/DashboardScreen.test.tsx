import { screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { DashboardScreen } from '@/features/dashboard/DashboardScreen';

import { getFormDrafts, resetForms } from '@/lib/formStore';
import { setSession } from '@/lib/sessionStore';
import type { SseMessage } from '@/types/chat.types';
import { PERSONAS, RESUMES, sessionFor } from '@/test/fixtures';
import { mockFetchRoutes, PENDING } from '@/test/mockFetch';
import { sseResponse } from '@/test/mockSse';
import { renderWithProviders } from '@/test/renderWithProviders';
import { LEE_ROUND_CHECK, LEE_ROUND_CHECK_SATISFIED } from '@/test/roundCheckFixture';

const push = vi.fn();
const replace = vi.fn();
vi.mock('next/navigation', () => ({ useRouter: () => ({ push, replace }) }));

const cards = PERSONAS.items;

/** 경로별로 응답을 나눕니다: 계정 카드는 JSON, 대화는 SSE 스트림. */
const mockApi = (chatEvents: SseMessage[] = []) =>
  vi.spyOn(globalThis, 'fetch').mockImplementation(async (input, init) => {
    const url = String(input);
    if (url.endsWith('/personas')) return Response.json({ items: cards, total: cards.length });
    // 대화 기록(GET)은 비어 있고, 보내기(POST)는 SSE 스트림입니다.
    if (url.endsWith('/messages') && init?.method === 'POST') return sseResponse(chatEvents);
    if (url.endsWith('/messages')) return Response.json({ items: [], total: 0, next_cursor: null });
    if (url.endsWith('/accounts/park/resume')) return Response.json(RESUMES.park);
    if (url.endsWith('/rounds/current')) return Response.json(LEE_ROUND_CHECK);
    return new Response('{}', { status: 404 });
  });

describe('DashboardScreen', () => {
  beforeEach(() => {
    resetForms();
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.clearAllMocks();
    setSession(null);
    document.documentElement.dataset.bigText = 'false';
  });

  it('세션이 없으면 로그인 화면으로 돌려보낸다', async () => {
    mockApi();
    renderWithProviders(<DashboardScreen />);

    await vi.waitFor(() => expect(replace).toHaveBeenCalledWith('/'));
  });

  it('이정호(E4b) 첫 화면: 진행바·제목·첫 안내·근거·선택지·D-day 카드', async () => {
    mockApi();
    setSession(sessionFor('lee'));

    renderWithProviders(<DashboardScreen />);

    expect(await screen.findByText('이정호님')).toBeInTheDocument();
    expect(screen.getByRole('heading', { level: 1, name: '이번 회차 할 일' })).toBeInTheDocument();
    expect(
      screen.getByText('다음 기한 : 4차 실업인정일 10.27(화) · 고용센터 출석'),
    ).toBeInTheDocument();
    expect(screen.getByLabelText('실업인정 현재 단계')).toBeInTheDocument();
    expect(screen.getByText(/3차 실업인정까지 받으셨네요/)).toBeInTheDocument();
    expect(screen.getAllByText(/실업인정 인정기준 · 2026.3.1 신청자부터/).length).toBeGreaterThan(
      0,
    );
    expect(screen.getByRole('button', { name: '부족한 활동 추천해 주세요' })).toBeInTheDocument();
    expect(await screen.findByText('D-6')).toBeInTheDocument();
    expect(screen.getByText(/~ 10\.27/)).toBeInTheDocument();
    expect(screen.getByText('고용센터 출석')).toBeInTheDocument();
    expect(document.documentElement.dataset.bigText).toBe('false');
  });

  it('최영수(E7b+M1+M4) 첫 화면: 글자 크게 기본 켜짐, 신청 경로 안내 상자', async () => {
    mockApi();
    setSession(sessionFor('choi'));

    renderWithProviders(<DashboardScreen />);

    expect(await screen.findByText(/2019년에 쓰신 이력서가 있네요/)).toBeInTheDocument();
    // 패널 상자와 함께 처음 한 번은 토스트로도 알립니다 (시연 개선 6번). 확인을 누르면 토스트만 닫힙니다.
    expect(screen.getAllByText('신청 경로 안내')).toHaveLength(2);
    await userEvent.click(within(screen.getByRole('status')).getByRole('button', { name: '확인' }));
    expect(screen.getAllByText('신청 경로 안내')).toHaveLength(1);
    // 크게 켜져 있으면 버튼 문구가 다음 동작인 `글자 보통`으로 보입니다.
    expect(screen.getByRole('button', { name: '글자 보통' })).toBeInTheDocument();
    expect(document.documentElement.dataset.bigText).toBe('true');
  });

  it('선택지를 누르면 보내고, 스트림의 token·form_update·ask_user·done이 화면과 저장소에 반영된다', async () => {
    const fetchSpy = mockApi([
      { event: 'tool_call', data: { name: 'check_activity_rules', status: 'started' } },
      { event: 'tool_call', data: { name: 'check_activity_rules', status: 'finished' } },
      { event: 'token', data: { text: '12월 16일 OO물산 ' } },
      { event: 'token', data: { text: '입사지원을 기록했어요.' } },
      {
        event: 'form_update',
        data: {
          form: 'activities',
          path: '/round_check',
          op: 'replace',
          value: LEE_ROUND_CHECK_SATISFIED,
        },
      },
      { event: 'done', data: { cite: '시험용 출처 자료' } },
      {
        event: 'ask_user',
        data: { question_id: 'q', text: '다음은요?', choices: ['신청서 볼게요'] },
      },
    ]);
    setSession(sessionFor('lee'));

    renderWithProviders(<DashboardScreen />);
    // 패널 B 점검 결과가 저장소에 들어간 뒤 보내야 스트림의 append가 덮어써지지 않습니다.
    expect(await screen.findByText('OO상사')).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: '새 활동 기록할게요' }));

    expect(await screen.findByText('12월 16일 OO물산 입사지원을 기록했어요.')).toBeInTheDocument();
    expect(await screen.findByRole('button', { name: '신청서 볼게요' })).toBeInTheDocument();
    expect(screen.getByText(/시험용 출처 자료/)).toBeInTheDocument();
    expect(
      screen.queryByRole('button', { name: '부족한 활동 추천해 주세요' }),
    ).not.toBeInTheDocument();
    const activities = getFormDrafts().activities.values.activities as { item_id: string }[];
    expect(activities.map((activity) => activity.item_id)).toEqual(['a1', 'a2', 'a3']);

    const chatCall = fetchSpy.mock.calls.find(
      ([input, init]) => String(input).endsWith('/messages') && init?.method === 'POST',
    );
    expect(chatCall?.[1]?.body).toBe(
      JSON.stringify({
        text: '새 활동 기록할게요',
        input_kind: 'choice',
        file_ids: [],
        import_ids: [],
      }),
    );
  });

  it('error 이벤트는 오류 문구를 보여 주고 보낸 글을 입력창에 되돌린다', async () => {
    mockApi([{ event: 'error', data: { code: 'LLM_UNAVAILABLE' } }]);
    setSession(sessionFor('park'));

    renderWithProviders(<DashboardScreen />);
    await userEvent.type(await screen.findByLabelText('메시지 입력'), '프레스 반장이었어요');
    await userEvent.click(screen.getByRole('button', { name: '보내기' }));

    const alerts = await screen.findAllByRole('alert');
    expect(alerts.some((a) => a.textContent?.includes('지금 답을 만들기 어려워요'))).toBe(true);
    expect(screen.getByLabelText('메시지 입력')).toHaveValue('프레스 반장이었어요');
  });

  it('계정 바꾸기를 누르면 세션을 지우고 로그인 화면으로 간다', async () => {
    mockApi();
    setSession(sessionFor('park'));

    renderWithProviders(<DashboardScreen />);
    await userEvent.click(await screen.findByRole('button', { name: '계정 바꾸기' }));

    expect(push).toHaveBeenCalledWith('/');
  });

  it('실제 서버 계정은 신청서 버튼이 대화 없이 바로 패널 C를 연다 (F-22)', async () => {
    const fetchSpy = mockFetchRoutes([
      [
        /\/accounts\/lee\/rounds\/current$/,
        {
          round: 4,
          period_start: '2026-11-25',
          period_end: '2026-12-22',
          recognition_date: '2026-12-22',
          attendance_required: true,
          status: 'current',
          application_status: 'draft',
          d_day: 6,
          required: 2,
          required_job_search: 1,
          counted: 2,
          remaining: 0,
          activities: [],
          required_evidence: [],
          limits_used: { lecture: 0, aptitude_test: 0, counseling: 0, volunteer: 0 },
          rule_review: 'not_verified',
        },
      ],
      // 신청서는 붙잡아 두고, 패널 C가 그 요청을 보내는지만 봅니다.
      [/\/accounts\/lee\/rounds\/4\/application$/, PENDING],
    ]);
    setSession({ ...sessionFor('lee'), session_id: 'acct-lee-2026-12-16' });

    renderWithProviders(<DashboardScreen />);
    await userEvent.click(
      await screen.findByRole('button', { name: '활동 정리 끝 · 신청서 만들기' }),
    );

    expect(await screen.findByText('신청서를 정리하는 중…')).toBeInTheDocument();
    const urls = fetchSpy.mock.calls.map(([input]) => String(input));
    expect(urls.some((url) => url.includes('/rounds/4/application'))).toBe(true);
    expect(urls.some((url) => url.includes('/chat'))).toBe(false);
  });
});

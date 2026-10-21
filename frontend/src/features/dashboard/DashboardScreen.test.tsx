import { screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { DashboardScreen } from '@/features/dashboard/DashboardScreen';

import { getFormDrafts, resetForms } from '@/lib/formStore';
import { setSession } from '@/lib/sessionStore';
import type { SseMessage } from '@/types/chat.types';
import { MOCK_ROUND_CHECKS } from '@/mocks/activities';
import { buildMockSession } from '@/mocks/handlers';
import { MOCK_PERSONAS } from '@/mocks/personas';
import { MOCK_RESUMES } from '@/mocks/resumes';
import { sseResponse } from '@/test/mockSse';
import { renderWithProviders } from '@/test/renderWithProviders';

const push = vi.fn();
const replace = vi.fn();
vi.mock('next/navigation', () => ({ useRouter: () => ({ push, replace }) }));

const cards = MOCK_PERSONAS.map(({ persona_id, display }) => ({ persona_id, display }));

/** 경로별로 응답을 나눕니다: 계정 카드는 JSON, 대화는 SSE 스트림. */
const mockApi = (chatEvents: SseMessage[] = []) =>
  vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
    const url = String(input);
    if (url.endsWith('/auth/demo')) return Response.json(cards);
    if (url.includes('/chat')) return sseResponse(chatEvents);
    if (url.endsWith('/forms/resume')) return Response.json(MOCK_RESUMES.park);
    if (url.endsWith('/procedure/current-round/check')) return Response.json(MOCK_ROUND_CHECKS.lee);
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
    setSession(buildMockSession('lee'));

    renderWithProviders(<DashboardScreen />);

    expect(await screen.findByText('이정호님')).toBeInTheDocument();
    expect(screen.getByRole('heading', { level: 1, name: '이번 회차 할 일' })).toBeInTheDocument();
    expect(
      screen.getByText('다음 기한 : 4차 실업인정일 12.22(화) · 고용센터 출석'),
    ).toBeInTheDocument();
    expect(screen.getByLabelText('실업인정 현재 단계')).toBeInTheDocument();
    expect(screen.getByText(/3차 실업인정까지 받으셨네요/)).toBeInTheDocument();
    expect(screen.getAllByText(/실업인정 인정기준 · 2026.3.1 신청자부터/).length).toBeGreaterThan(
      0,
    );
    expect(screen.getByRole('button', { name: '부족한 활동 추천해 주세요' })).toBeInTheDocument();
    expect(await screen.findByText('D-6')).toBeInTheDocument();
    expect(screen.getByText('11.25 ~ 12.22')).toBeInTheDocument();
    expect(screen.getByText('고용센터 출석')).toBeInTheDocument();
    expect(document.documentElement.dataset.bigText).toBe('false');
  });

  it('최영수(E7b+M1+M4) 첫 화면: 글자 크게 기본 켜짐, 신청 경로 안내 상자', async () => {
    mockApi();
    setSession(buildMockSession('choi'));

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
          path: 'activities',
          op: 'append',
          value: {
            ...MOCK_ROUND_CHECKS.lee.activities[0],
            item_id: 'a3',
            date: '2026-12-16',
            org_name: 'OO물산',
          },
        },
      },
      { event: 'done', data: { cite: '시험용 출처 자료' } },
      {
        event: 'ask_user',
        data: { question_id: 'q', text: '다음은요?', choices: ['신청서 볼게요'] },
      },
    ]);
    setSession(buildMockSession('lee'));

    renderWithProviders(<DashboardScreen />);
    // 패널 B 점검 결과가 저장소에 들어간 뒤 보내야 스트림의 append가 덮어써지지 않습니다.
    expect(await screen.findByText('OO상사')).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: '이미 한 활동 기록할게요' }));

    expect(await screen.findByText('12월 16일 OO물산 입사지원을 기록했어요.')).toBeInTheDocument();
    expect(await screen.findByRole('button', { name: '신청서 볼게요' })).toBeInTheDocument();
    expect(screen.getByText(/시험용 출처 자료/)).toBeInTheDocument();
    expect(
      screen.queryByRole('button', { name: '부족한 활동 추천해 주세요' }),
    ).not.toBeInTheDocument();
    const activities = getFormDrafts().activities.values.activities as { item_id: string }[];
    expect(activities.map((activity) => activity.item_id)).toEqual(['a1', 'a2', 'a3']);

    const chatCall = fetchSpy.mock.calls.find(([input]) => String(input).includes('/chat'));
    expect(chatCall?.[1]?.body).toBe(
      JSON.stringify({ message: '이미 한 활동 기록할게요', input_kind: 'choice' }),
    );
  });

  it('error 이벤트는 오류 문구를 보여 주고 보낸 글을 입력창에 되돌린다', async () => {
    mockApi([{ event: 'error', data: { code: 'LLM_UNAVAILABLE' } }]);
    setSession(buildMockSession('park'));

    renderWithProviders(<DashboardScreen />);
    await userEvent.type(await screen.findByLabelText('메시지 입력'), '프레스 반장이었어요');
    await userEvent.click(screen.getByRole('button', { name: '보내기' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('지금 답을 만들기 어려워요');
    expect(screen.getByLabelText('메시지 입력')).toHaveValue('프레스 반장이었어요');
  });

  it('계정 바꾸기를 누르면 세션을 지우고 로그인 화면으로 간다', async () => {
    mockApi();
    setSession(buildMockSession('park'));

    renderWithProviders(<DashboardScreen />);
    await userEvent.click(await screen.findByRole('button', { name: '계정 바꾸기' }));

    expect(push).toHaveBeenCalledWith('/');
  });
});

import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { DashboardScreen } from '@/features/dashboard/DashboardScreen';

import { setSession } from '@/lib/sessionStore';
import { buildMockSession } from '@/mocks/handlers';
import { MOCK_PERSONAS } from '@/mocks/personas';
import { mockFetchJson } from '@/test/mockFetch';
import { renderWithProviders } from '@/test/renderWithProviders';

const push = vi.fn();
const replace = vi.fn();
vi.mock('next/navigation', () => ({ useRouter: () => ({ push, replace }) }));

const cards = MOCK_PERSONAS.map(({ persona_id, display }) => ({ persona_id, display }));

describe('DashboardScreen', () => {
  beforeEach(() => {
    mockFetchJson(cards);
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.clearAllMocks();
    setSession(null);
    document.documentElement.dataset.bigText = 'false';
  });

  it('세션이 없으면 로그인 화면으로 돌려보낸다', async () => {
    renderWithProviders(<DashboardScreen />);

    await vi.waitFor(() => expect(replace).toHaveBeenCalledWith('/'));
  });

  it('이정호(E4b) 첫 화면: 진행바·제목·첫 안내·근거·선택지·D-day 카드', async () => {
    setSession(buildMockSession('lee'));

    renderWithProviders(<DashboardScreen />);

    expect(await screen.findByText('이정호님')).toBeInTheDocument();
    expect(screen.getByRole('heading', { level: 1, name: '이번 회차 할 일' })).toBeInTheDocument();
    expect(
      screen.getByText('다음 기한 : 4차 실업인정일 12.22(화) · 고용센터 출석'),
    ).toBeInTheDocument();
    expect(screen.getByLabelText('실업인정 현재 단계')).toBeInTheDocument();
    expect(screen.getByText(/3차 실업인정까지 받으셨네요/)).toBeInTheDocument();
    expect(screen.getByText(/실업인정 인정기준 안내문/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '부족한 활동 추천해 주세요' })).toBeInTheDocument();
    expect(screen.getByText('D-6')).toBeInTheDocument();
    expect(screen.getByText('11.25 ~ 12.22')).toBeInTheDocument();
    expect(screen.getByText('고용센터 출석')).toBeInTheDocument();
    expect(document.documentElement.dataset.bigText).toBe('false');
  });

  it('최영수(E7b+M1+M4) 첫 화면: 글자 크게 기본 켜짐, 신청 경로 안내 상자', async () => {
    setSession(buildMockSession('choi'));

    renderWithProviders(<DashboardScreen />);

    expect(await screen.findByText(/2019년에 쓰신 이력서가 있네요/)).toBeInTheDocument();
    expect(screen.getByText('신청 경로 안내')).toBeInTheDocument();
    // 크게 켜져 있으면 버튼 문구가 다음 동작인 `글자 보통`으로 보입니다.
    expect(screen.getByRole('button', { name: '글자 보통' })).toBeInTheDocument();
    expect(document.documentElement.dataset.bigText).toBe('true');
  });

  it('선택지를 누르면 사용자 말풍선이 생기고 선택지는 사라진다', async () => {
    setSession(buildMockSession('park'));

    renderWithProviders(<DashboardScreen />);
    await userEvent.click(await screen.findByRole('button', { name: '사진부터 올릴게요' }));

    expect(screen.getByText('사진부터 올릴게요')).toBeInTheDocument();
    expect(screen.queryByRole('group', { name: '선택지' })).not.toBeInTheDocument();
  });

  it('계정 바꾸기를 누르면 세션을 지우고 로그인 화면으로 간다', async () => {
    setSession(buildMockSession('park'));

    renderWithProviders(<DashboardScreen />);
    await userEvent.click(await screen.findByRole('button', { name: '계정 바꾸기' }));

    expect(push).toHaveBeenCalledWith('/');
  });
});

import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { PersonaList } from '@/features/auth/PersonaList';

import { getSession, setSession } from '@/lib/sessionStore';
import { ACCOUNTS, PERSONAS } from '@/test/fixtures';
import { mockFetchJson } from '@/test/mockFetch';
import { renderWithProviders } from '@/test/renderWithProviders';

const push = vi.fn();
vi.mock('next/navigation', () => ({ useRouter: () => ({ push, replace: vi.fn() }) }));

const list = PERSONAS;

describe('PersonaList', () => {
  afterEach(() => {
    vi.restoreAllMocks();
    setSession(null);
  });

  it('가상 계정 카드를 이름·나이·직종·한마디·상태 요약과 함께 보여준다', async () => {
    mockFetchJson(list);

    renderWithProviders(<PersonaList />);

    expect(await screen.findByRole('button', { name: '박진수 계정으로 시작' })).toBeInTheDocument();
    expect(screen.getByText('수급 중 · 4차 실업인정 준비 · 이력서 있음')).toBeInTheDocument();
    expect(screen.getAllByRole('button')).toHaveLength(3);
  });

  it('카드마다 이 계정으로 해 볼 수 있는 일을 설명으로 붙인다', async () => {
    mockFetchJson(list);

    renderWithProviders(<PersonaList />);

    const card = await screen.findByRole('button', { name: '박진수 계정으로 시작' });
    expect(card).toHaveAccessibleDescription(
      /경력증명서 사진을 올리면 회사·기간·하던 일을 읽어 이력서 칸에 넣어요/,
    );
  });

  it('카드를 누르면 계정에 입장(PUT /accounts/lee)하고 대시보드로 간다', async () => {
    const fetchSpy = mockFetchJson(list);
    fetchSpy
      .mockResolvedValueOnce(Response.json(list))
      .mockResolvedValueOnce(Response.json(ACCOUNTS.lee, { status: 201 }));

    renderWithProviders(<PersonaList />);
    await userEvent.click(await screen.findByRole('button', { name: '이정호 계정으로 시작' }));

    await vi.waitFor(() => expect(push).toHaveBeenCalledWith('/dashboard'));
    expect(getSession()?.entry.branch_id).toBe('E4b');
    const [url, init] = fetchSpy.mock.calls[1];
    expect(url).toBe('/api/accounts/lee');
    expect(init?.method).toBe('PUT');
  });

  it('목록을 못 받으면 안내 문구를 보여준다', async () => {
    mockFetchJson({ detail: 'error' }, { status: 500 });

    renderWithProviders(<PersonaList />);

    expect(await screen.findByRole('alert')).toHaveTextContent('계정 목록을 불러오지 못했어요');
  });
});

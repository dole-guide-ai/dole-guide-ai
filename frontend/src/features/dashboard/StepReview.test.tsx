import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { DashboardScreen } from '@/features/dashboard/DashboardScreen';

import { resetForms } from '@/lib/formStore';
import { setSession } from '@/lib/sessionStore';
import { buildMockSession } from '@/mocks/handlers';
import { MOCK_PERSONAS } from '@/mocks/personas';
import { MOCK_RESUMES } from '@/mocks/resumes';
import { renderWithProviders } from '@/test/renderWithProviders';
import { LEE_ROUND_CHECK } from '@/test/roundCheckFixture';

vi.mock('next/navigation', () => ({ useRouter: () => ({ push: vi.fn(), replace: vi.fn() }) }));

const cards = MOCK_PERSONAS.map(({ persona_id, display }) => ({ persona_id, display }));

describe('완료 단계 읽기 전용 다시 보기 (1.8)', () => {
  beforeEach(() => {
    resetForms();
    vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
      const url = String(input);
      if (url.endsWith('/personas')) return Response.json({ items: cards, total: cards.length });
      if (url.endsWith('/forms/resume')) return Response.json(MOCK_RESUMES.lee);
      if (url.endsWith('/rounds/current')) return Response.json(LEE_ROUND_CHECK);
      return new Response('{}', { status: 404 });
    });
    setSession(buildMockSession('lee'));
  });

  afterEach(() => {
    vi.restoreAllMocks();
    setSession(null);
  });

  it('구직등록을 누르면 저장된 이력서를 읽기 전용으로 보여 주고, 돌아가기로 이번 단계에 온다', async () => {
    renderWithProviders(<DashboardScreen />);

    await userEvent.click(
      await screen.findByRole('button', { name: '구직등록 단계 다시 보기 (완료)' }),
    );

    expect(await screen.findByText('OO유통')).toBeInTheDocument();
    expect(screen.getByText('완료한 단계 · 이력서 (읽기 전용)')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '확인하고 이력서 저장' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '고치기' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '직접 입력' })).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole('button', { name: '이번 단계로 돌아가기' }));
    expect(await screen.findByLabelText('필요 활동 결과')).toBeInTheDocument();
  });

  it('수급자격 신청을 누르면 신청 완료 상태의 패널 Q를 보여 준다', async () => {
    renderWithProviders(<DashboardScreen />);

    await userEvent.click(
      await screen.findByRole('button', { name: '수급자격 신청 단계 다시 보기 (완료)' }),
    );

    expect(screen.getByText('완료한 단계 · 수급자격 신청 (읽기 전용)')).toBeInTheDocument();
    expect(screen.getByText('신청 완료')).toBeInTheDocument();
  });
});

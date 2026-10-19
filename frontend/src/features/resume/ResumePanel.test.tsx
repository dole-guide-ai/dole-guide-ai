import { act, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { ResumePanel } from '@/features/resume/ResumePanel';

import { applyFormUpdate, resetForms } from '@/lib/formStore';
import { getSession, setSession } from '@/lib/sessionStore';
import { MOCK_AFTER_RESUME_ENTRIES } from '@/mocks/entries';
import { buildMockSession } from '@/mocks/handlers';
import { MOCK_RESUMES } from '@/mocks/resumes';
import { renderWithProviders } from '@/test/renderWithProviders';

const mockApi = (personaId: 'park' | 'choi') =>
  vi.spyOn(globalThis, 'fetch').mockImplementation(async (input, init) => {
    const url = String(input);
    if (url.endsWith('/forms/resume')) return Response.json(MOCK_RESUMES[personaId]);
    if (url.endsWith('/forms/resume/confirm') && init?.method === 'POST') {
      const session = buildMockSession(personaId);
      return Response.json({ ...session, entry: MOCK_AFTER_RESUME_ENTRIES[personaId] });
    }
    return Response.json({ code: 'NOT_FOUND', message: '없는 경로예요.' }, { status: 404 });
  });

describe('ResumePanel', () => {
  beforeEach(() => resetForms());

  afterEach(() => {
    vi.restoreAllMocks();
    setSession(null);
  });

  it('최영수(E7b): 예전 이력서 값과 확인 필요, 완성도 3/5, 저장 버튼 비활성', async () => {
    mockApi('choi');
    const session = buildMockSession('choi');

    renderWithProviders(<ResumePanel session={session} />);

    expect(await screen.findByLabelText('완성도')).toHaveTextContent('3 / 5');
    expect(screen.getAllByText('예전 이력서').length).toBeGreaterThan(0);
    expect(screen.getAllByText('확인 필요').length).toBeGreaterThan(0);
    expect(screen.getByText('OO아파트 관리사무소')).toBeInTheDocument();
    expect(screen.getByText('전기기능사 · 한국산업인력공단 · 2009.11.20')).toBeInTheDocument();
    expect(screen.getAllByText('필수')).toHaveLength(2);
    expect(screen.getByRole('button', { name: '확인하고 이력서 최신화' })).toBeDisabled();
  });

  it('박진수(E7a): 빈 양식은 필수 5개가 모두 남고 다음 질문이 보인다', async () => {
    mockApi('park');

    renderWithProviders(<ResumePanel session={buildMockSession('park')} />);

    expect(await screen.findByLabelText('완성도')).toHaveTextContent('0 / 5');
    expect(screen.getAllByText('필수')).toHaveLength(5);
    expect(screen.getByText(/AI가 이어서 물어볼 것 · 가장 최근에 일하신 곳/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '확인하고 이력서 저장' })).toBeDisabled();
  });

  it('form_update로 칸이 채워지면 칩·근거가 바뀌고, 고치기는 항목 이름을 넘긴다', async () => {
    mockApi('park');
    const onEditRequest = vi.fn();

    renderWithProviders(
      <ResumePanel session={buildMockSession('park')} onEditRequest={onEditRequest} />,
    );
    await screen.findByLabelText('완성도');

    act(() => {
      applyFormUpdate({
        form: 'resume',
        path: 'resume_title',
        op: 'set',
        value: '프레스 반장 22년',
        status: 'extracted',
        source: 'conversation',
        transformed: true,
        evidence: {
          kind: 'utterance',
          date: '2026-10-12',
          quote: '프레스 22년',
          note: '제목 제안',
        },
      });
    });

    const titleSection = screen.getByRole('heading', { name: '이력서 제목' }).closest('section')!;
    expect(within(titleSection).getByText('프레스 반장 22년')).toBeInTheDocument();
    expect(within(titleSection).getByText('확인 필요')).toBeInTheDocument();
    expect(within(titleSection).getByText(/제목 제안/)).toBeInTheDocument();

    await userEvent.click(within(titleSection).getByRole('button', { name: '고치기' }));
    expect(onEditRequest).toHaveBeenCalledWith('이력서 제목');
  });

  it('can_save가 켜지면 저장할 수 있고, 저장하면 세션이 온라인 교육 단계로 바뀐다', async () => {
    mockApi('choi');
    setSession(buildMockSession('choi'));

    renderWithProviders(<ResumePanel session={getSession()!} />);
    await screen.findByLabelText('완성도');
    act(() => {
      applyFormUpdate({ form: 'resume', path: 'can_save', op: 'set', value: true });
    });

    const button = screen.getByRole('button', { name: '확인하고 이력서 최신화' });
    expect(button).toBeEnabled();
    await userEvent.click(button);

    await vi.waitFor(() => expect(getSession()?.entry.branch_id).toBe('E6'));
    expect(getSession()?.entry.panel).toBe('E');
  });
});

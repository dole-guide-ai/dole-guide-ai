import { act, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { ResumePanel } from '@/features/resume/ResumePanel';

import { applyFormUpdate, resetForms } from '@/lib/formStore';
import { getSession, setSession } from '@/lib/sessionStore';
import { mockResumeApi, RESUMES, sessionFor } from '@/test/fixtures';
import { renderWithProviders } from '@/test/renderWithProviders';

describe('ResumePanel (실제 이력서 API 응답)', () => {
  beforeEach(() => resetForms());

  afterEach(() => {
    vi.restoreAllMocks();
    setSession(null);
  });

  it('최영수(E7b): 예전 이력서 값과 예전 이력서 칩, 저장 버튼 비활성', async () => {
    mockResumeApi('choi');

    renderWithProviders(<ResumePanel session={sessionFor('choi')} />);

    // 백엔드 완성도는 4/5 (상세기획 1.9는 3/5, 설계와 다른 점으로 보고함)
    expect(await screen.findByLabelText('완성도')).toHaveTextContent(
      `${RESUMES.choi.completeness.filled} / 5`,
    );
    expect(screen.getAllByText('예전 이력서').length).toBeGreaterThan(0);
    expect(screen.getByText('OO아파트 관리사무소')).toBeInTheDocument();
    expect(screen.getByText('전기기능사')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '확인하고 이력서 최신화' })).toBeDisabled();
  });

  it('박진수(E7a): 빈 양식은 필수 칸이 남고 저장할 수 없다', async () => {
    mockResumeApi('park');

    renderWithProviders(<ResumePanel session={sessionFor('park')} />);

    expect(await screen.findByLabelText('완성도')).toHaveTextContent('0 / 5');
    expect(screen.getAllByText('필수').length).toBeGreaterThan(0);
    expect(screen.getByRole('button', { name: '확인하고 이력서 저장' })).toBeDisabled();
  });

  it('운전·차량은 비어 있으면 `선택` 칩이다 (시연 검증 7번)', async () => {
    mockResumeApi('park');

    renderWithProviders(<ResumePanel session={sessionFor('park')} />);

    for (const label of ['운전가능', '차량소지']) {
      const row = (await screen.findByText(label)).closest('div')!;
      expect(within(row).getByText('선택')).toBeInTheDocument();
    }
  });

  it('form_update로 칸이 채워지면 칩·근거가 바뀌고, 고치기는 항목 이름을 넘긴다', async () => {
    mockResumeApi('park');
    const onEditRequest = vi.fn();

    renderWithProviders(<ResumePanel session={sessionFor('park')} onEditRequest={onEditRequest} />);
    await screen.findByLabelText('완성도');

    act(() => {
      applyFormUpdate({
        form: 'resume',
        path: '/resume_title',
        op: 'replace',
        value: '프레스 반장 22년',
        status: 'extracted',
        source: 'self_answer',
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

  it('저장할 수 있으면 PATCH /status saved를 보내고 세션이 온라인 교육(E6)으로 바뀐다 (F-15)', async () => {
    const { patches } = mockResumeApi('choi', { ...RESUMES.choi, can_save: true });
    setSession(sessionFor('choi'));

    renderWithProviders(<ResumePanel session={getSession()!} />);
    const button = await screen.findByRole('button', { name: '확인하고 이력서 최신화' });
    await vi.waitFor(() => expect(button).toBeEnabled());
    await userEvent.click(button);

    await vi.waitFor(() => expect(getSession()?.entry.branch_id).toBe('E6'));
    expect(patches).toEqual([{ op: 'replace', path: '/status', value: 'saved' }]);
  });
});

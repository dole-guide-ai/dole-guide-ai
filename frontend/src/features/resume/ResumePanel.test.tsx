import { act, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { ResumePanel } from '@/features/resume/ResumePanel';

import { applyFormUpdate, getFormDrafts, resetForms } from '@/lib/formStore';
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
    expect(screen.getByText('전기기능사')).toBeInTheDocument();
    expect(screen.getByText('2009.11.20')).toBeInTheDocument();
    expect(screen.getAllByText('필수')).toHaveLength(2);
    expect(screen.getByRole('button', { name: '확인하고 이력서 최신화' })).toBeDisabled();
  });

  it('공통코드로 확정되지 않은 직종은 확인 필요 표시를 붙인다 (데이터 설계 7.7)', async () => {
    mockApi('choi');

    renderWithProviders(<ResumePanel session={buildMockSession('choi')} />);

    // 희망직종과 경력의 직종 두 곳
    expect(await screen.findAllByText('시설관리 (직종 확인 필요)')).toHaveLength(2);
  });

  it('학력은 최종학력을 표시하고, 대학 이상인데 학점이 비면 고용24 입력 때 필요하다고 남긴다 (2-1.2 · 2-1.8)', async () => {
    const choi = MOCK_RESUMES.choi;
    vi.spyOn(globalThis, 'fetch').mockImplementation(async () =>
      Response.json({
        ...choi,
        education: [
          ...choi.education,
          {
            item_id: 'edu_002',
            level: '대학교(4년제)',
            graduation_status: '졸업',
            school_name: 'OO대학교',
            start_date: '1979-03',
            end_date: '1983-02',
            major: '경영학',
            gpa: null,
          },
        ],
      }),
    );

    renderWithProviders(<ResumePanel session={buildMockSession('choi')} />);

    expect(await screen.findByText('고등학교 · 최종학력')).toBeInTheDocument();
    expect(screen.getByText('1975.03 ~ 1978.02')).toBeInTheDocument();
    expect(screen.getByText('경영학')).toBeInTheDocument();
    expect(screen.getByText('빈칸 (고용24 입력 때 필요)')).toBeInTheDocument();
  });

  it('선택형 칸은 고용24 선택지에서 골라 직접 저장하고, 선택 항목 칩은 `선택`이다 (시연 개선 8·9번)', async () => {
    const fetchSpy = mockApi('choi');
    fetchSpy.mockImplementation(async (input, init) => {
      const url = String(input);
      if (url.endsWith('/forms/resume') && init?.method === 'PATCH') {
        const body = JSON.parse(String(init.body)) as { path: string; value: unknown };
        return Response.json({
          updates: [
            {
              form: 'resume',
              path: body.path,
              op: 'set',
              value: body.value,
              status: 'confirmed',
              source: 'manual',
            },
          ],
        });
      }
      return Response.json(MOCK_RESUMES.choi);
    });

    renderWithProviders(<ResumePanel session={buildMockSession('choi')} />);

    const contract = (await screen.findByText('고용형태')).closest('div')!;
    await userEvent.click(within(contract).getByRole('button', { name: '직접 입력' }));
    await userEvent.selectOptions(screen.getByLabelText('고용형태 직접 입력'), '관계없음');
    await userEvent.click(within(contract).getByRole('button', { name: '저장' }));

    expect(await within(contract).findByText('관계없음')).toBeInTheDocument();
    expect(within(contract).getByText('직접 입력', { selector: 'span' })).toBeInTheDocument();
    expect(screen.getAllByText('선택').length).toBeGreaterThan(0);
    expect(screen.queryByText('있으면', { selector: 'span' })).not.toBeInTheDocument();
  });

  it('직종처럼 값만 있고 저장 상태가 없는 칸에는 `아직 없음` 칩을 달지 않는다 (PPT 점검 N1)', async () => {
    mockApi('choi');

    renderWithProviders(<ResumePanel session={buildMockSession('choi')} />);

    const occupationRow = (await screen.findAllByText('시설관리 (직종 확인 필요)'))[1].closest(
      'div',
    )!;
    expect(within(occupationRow).queryByText('아직 없음')).not.toBeInTheDocument();
  });

  it('컴퓨터 활용(객체)과 기타자격을 보여 준다', async () => {
    const park = MOCK_RESUMES.park;
    vi.spyOn(globalThis, 'fetch').mockImplementation(async () =>
      Response.json({
        ...park,
        competencies: {
          ...park.competencies,
          computer_skills: { selected_skills: ['문서작성', '표계산'], other_skills: '한글' },
          other_certifications: ['민간 OO자격'],
        },
      }),
    );

    renderWithProviders(<ResumePanel session={buildMockSession('park')} />);

    expect(await screen.findByText('문서작성, 표계산, 한글')).toBeInTheDocument();
    expect(screen.getByText('민간 OO자격')).toBeInTheDocument();
  });

  it('박진수(E7a): 빈 양식은 필수 5개가 모두 남고 다음 질문이 보인다', async () => {
    mockApi('park');

    renderWithProviders(<ResumePanel session={buildMockSession('park')} />);

    expect(await screen.findByLabelText('완성도')).toHaveTextContent('0 / 5');
    expect(screen.getAllByText('필수')).toHaveLength(5);
    const order = screen.getByRole('region', { name: 'AI가 물어볼 순서' });
    expect(within(order).getByText('1. 가장 최근에 일하신 곳 (지금)')).toBeInTheDocument();
    expect(within(order).getByText('4. 자격증·면허')).toBeInTheDocument();
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

  it('저장한 이력서는 고치면 다시 저장하기로 재확정하고, 단계는 그대로 둔다 (2-1.6)', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation(async (input, init) => {
      const url = String(input);
      if (url.endsWith('/forms/resume')) return Response.json(MOCK_RESUMES.lee);
      if (url.endsWith('/forms/resume/confirm') && init?.method === 'POST') {
        return Response.json(buildMockSession('lee'));
      }
      return Response.json({ code: 'NOT_FOUND', message: '없는 경로예요.' }, { status: 404 });
    });
    setSession(buildMockSession('lee'));
    const onSaved = vi.fn();

    renderWithProviders(
      <ResumePanel session={getSession()!} saveLabel="다시 저장하기" onSaved={onSaved} />,
    );
    await screen.findByLabelText('완성도');
    act(() => {
      applyFormUpdate({ form: 'resume', path: 'status', op: 'set', value: 'draft' });
      applyFormUpdate({ form: 'resume', path: 'can_save', op: 'set', value: true });
    });
    await userEvent.click(screen.getByRole('button', { name: '다시 저장하기' }));

    await vi.waitFor(() => expect(onSaved).toHaveBeenCalled());
    expect(getFormDrafts().resume.values.status).toBe('finalized');
    expect(getSession()?.state.stage).toBe('recognition');
    expect(screen.getByText('경력 25년 5개월')).toBeInTheDocument();
  });
});

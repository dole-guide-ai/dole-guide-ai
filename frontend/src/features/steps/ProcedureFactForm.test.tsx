import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { ProcedureFactForm } from '@/features/steps/ProcedureFactForm';

import { getSession, setSession } from '@/lib/sessionStore';
import { mockAccount } from '@/mocks/handlers';
import { mockFetchJson } from '@/test/mockFetch';
import { renderWithProviders } from '@/test/renderWithProviders';

const res = (body: unknown, status = 200) => Response.json(body, { status });

const renderEducation = () =>
  renderWithProviders(
    <ProcedureFactForm personaId="choi" path="/education_done" buttonLabel="교육을 다 들었어요" />,
  );
const clickEducation = () =>
  userEvent.click(screen.getByRole('button', { name: '교육을 다 들었어요' }));

describe('ProcedureFactForm (F-16)', () => {
  afterEach(() => {
    vi.restoreAllMocks();
    setSession(null);
  });

  it('교육 이수를 누르면 PATCH 뒤 계정을 다시 불러와 세션 단계를 바꾼다', async () => {
    const next = mockAccount('choi');
    next.procedure.stage = 'eligibility_application';
    next.entry.branch_id = 'E5a';
    next.entry.panel = 'Q';
    const fetchSpy = mockFetchJson(next).mockResolvedValueOnce(res({ updates: [] }));

    renderEducation();
    await clickEducation();

    await vi.waitFor(() => expect(getSession()?.state.stage).toBe('eligibility_application'));
    const [url, init] = fetchSpy.mock.calls[0];
    expect(String(url)).toBe('/api/accounts/choi/procedure');
    expect(JSON.parse(String(init?.body))).toEqual([
      { op: 'replace', path: '/education_done', value: true },
    ]);
    expect(getSession()?.entry.panel).toBe('Q');
  });

  it('날짜 칸이 있으면 고른 날짜를 보낸다', async () => {
    const fetchSpy = mockFetchJson(mockAccount('choi')).mockResolvedValueOnce(res({ updates: [] }));

    renderWithProviders(
      <ProcedureFactForm
        personaId="choi"
        path="/eligibility_applied_on"
        dateLabel="수급자격 신청일"
        defaultDate="2026-10-21"
        buttonLabel="신청을 마쳤어요"
      />,
    );
    const input = screen.getByLabelText('수급자격 신청일');
    await userEvent.clear(input);
    await userEvent.type(input, '2026-10-12');
    await userEvent.click(screen.getByRole('button', { name: '신청을 마쳤어요' }));

    await vi.waitFor(() => expect(fetchSpy).toHaveBeenCalledTimes(2));
    expect(JSON.parse(String(fetchSpy.mock.calls[0][1]?.body))).toEqual([
      { op: 'replace', path: '/eligibility_applied_on', value: '2026-10-12' },
    ]);
  });

  it('단계 순서가 틀리면 서버가 쓴 문구를 보여 준다', async () => {
    const message = '이력서를 저장한 뒤에 교육 이수를 표시할 수 있어요.';
    mockFetchJson({ code: 'STAGE_ORDER', message, details: null }, { status: 409 });

    renderEducation();
    await clickEducation();

    expect(await screen.findByRole('alert')).toHaveTextContent(message);
  });

  it('저장 뒤 계정 다시 불러오기만 실패하면 다시 보내지 않고 다시 불러오기만 권한다', async () => {
    const next = mockAccount('choi');
    next.procedure.stage = 'eligibility_application';
    const fetchSpy = mockFetchJson(next)
      .mockResolvedValueOnce(res({ updates: [] }))
      .mockResolvedValueOnce(res({ code: 'INTERNAL_ERROR', message: '잠시 뒤에요.' }, 500));

    renderEducation();
    await clickEducation();

    expect(
      await screen.findByText('저장했어요. 화면을 새로 불러오지 못했어요.'),
    ).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '교육을 다 들었어요' })).toBeDisabled();
    await userEvent.click(screen.getByRole('button', { name: '화면 다시 불러오기' }));

    await vi.waitFor(() => expect(getSession()?.state.stage).toBe('eligibility_application'));
    expect(fetchSpy.mock.calls.filter(([, init]) => init?.method === 'PATCH')).toHaveLength(1);
  });
});

import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { ImportPicker } from '@/features/imports/ImportPicker';

import { MOCK_IMPORTS } from '@/mocks/imports';
import { mockFetchJson } from '@/test/mockFetch';
import { renderWithProviders } from '@/test/renderWithProviders';

describe('ImportPicker', () => {
  afterEach(() => vi.restoreAllMocks());

  it('아무것도 고르지 않은 채로 열고, 고른 것만 넘긴다 (2-1.5)', async () => {
    mockFetchJson(MOCK_IMPORTS['career-certificate'].park);
    const onApply = vi.fn();

    renderWithProviders(
      <ImportPicker kind="career-certificate" sessionId="s1" onApply={onApply} />,
    );

    const apply = await screen.findByRole('button', { name: '넣을 항목을 골라 주세요' });
    expect(apply).toBeDisabled();

    await userEvent.click(screen.getByRole('checkbox', { name: /OO산업/ }));
    await userEvent.click(screen.getByRole('checkbox', { name: /지게차운전기능사/ }));
    await userEvent.click(screen.getByRole('button', { name: '고른 2건 넣기' }));

    expect(onApply).toHaveBeenCalledWith(['cc_career_001', 'cc_license_001']);
  });

  it('이미 넣은 항목은 고를 수 없다', async () => {
    mockFetchJson(MOCK_IMPORTS['work24-activities'].lee);

    renderWithProviders(<ImportPicker kind="work24-activities" sessionId="s1" onApply={vi.fn()} />);

    expect(await screen.findByRole('checkbox', { name: /OO물류/ })).toBeDisabled();
    expect(screen.getByRole('checkbox', { name: /OO물산/ })).toBeEnabled();
    expect(screen.getByText('이미 넣음')).toBeInTheDocument();
  });

  it('목록을 못 받으면 서버 문구를 보여 준다', async () => {
    mockFetchJson({ code: 'INTERNAL_ERROR', message: '불러오기에 실패했어요.' }, { status: 500 });

    renderWithProviders(
      <ImportPicker kind="career-certificate" sessionId="s1" onApply={vi.fn()} />,
    );

    expect(await screen.findByRole('alert')).toHaveTextContent('불러오기에 실패했어요.');
  });
});

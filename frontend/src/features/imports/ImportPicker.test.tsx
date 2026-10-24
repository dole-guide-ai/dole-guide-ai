import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { ImportPicker } from '@/features/imports/ImportPicker';

import { mockFetchJson } from '@/test/mockFetch';
import { renderWithProviders } from '@/test/renderWithProviders';

const item = (import_id: string, category: string, title: string, is_recorded = false) => ({
  import_id,
  is_recorded,
  values: { category, title, detail: '합성 설명' },
});

/** `GET /accounts/{id}/imports/...` 응답 (합성 값) */
const CAREERS = {
  items: [
    item('cc_career_001', 'career', 'OO산업'),
    item('cc_license_001', 'license', '지게차운전기능사'),
  ],
  total: 2,
  source_note: '모의 목록이에요.',
};
const APPLICATIONS = {
  items: [
    item('wa_001', 'job_search', 'OO물류 · 일반 사무', true),
    item('wa_003', 'job_search', 'OO물산 · 사무보조'),
  ],
  total: 2,
  source_note: '모의 목록이에요.',
};

describe('ImportPicker', () => {
  afterEach(() => vi.restoreAllMocks());

  it('아무것도 고르지 않은 채로 열고, 고른 것만 넘긴다 (2-1.5)', async () => {
    mockFetchJson(CAREERS);
    const onApply = vi.fn();

    renderWithProviders(
      <ImportPicker kind="career-certificate" sessionId="s1" personaId="lee" onApply={onApply} />,
    );

    const apply = await screen.findByRole('button', { name: '넣을 항목을 골라 주세요' });
    expect(apply).toBeDisabled();

    await userEvent.click(screen.getByRole('checkbox', { name: /OO산업/ }));
    await userEvent.click(screen.getByRole('checkbox', { name: /지게차운전기능사/ }));
    await userEvent.click(screen.getByRole('button', { name: '고른 2건 넣기' }));

    expect(onApply).toHaveBeenCalledWith(['cc_career_001', 'cc_license_001']);
  });

  it('이미 넣은 항목은 고를 수 없다', async () => {
    mockFetchJson(APPLICATIONS);

    renderWithProviders(
      <ImportPicker kind="work24-activities" sessionId="s1" personaId="lee" onApply={vi.fn()} />,
    );

    expect(await screen.findByRole('checkbox', { name: /OO물류/ })).toBeDisabled();
    expect(screen.getByRole('checkbox', { name: /OO물산/ })).toBeEnabled();
    expect(screen.getByText('이미 넣음')).toBeInTheDocument();
  });

  it('목록을 못 받으면 서버 문구를 보여 준다', async () => {
    mockFetchJson({ code: 'INTERNAL_ERROR', message: '불러오기에 실패했어요.' }, { status: 500 });

    renderWithProviders(
      <ImportPicker kind="career-certificate" sessionId="s1" personaId="lee" onApply={vi.fn()} />,
    );

    expect(await screen.findByRole('alert')).toHaveTextContent('불러오기에 실패했어요.');
  });
});

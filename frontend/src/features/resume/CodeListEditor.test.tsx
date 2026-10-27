import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { CodeListEditor } from '@/features/resume/CodeListEditor';

import { ApiError } from '@/lib/api';
import electric from '@/test/fixtures/codes_occupations_electric.json';
import regions from '@/test/fixtures/codes_regions.json';
import { mockFetchRoutes } from '@/test/mockFetch';
import { renderWithProviders } from '@/test/renderWithProviders';

afterEach(() => vi.restoreAllMocks());

describe('CodeListEditor', () => {
  it('직종은 찾아서 고른 코드와 이름만 적기를 함께 저장합니다', async () => {
    mockFetchRoutes([[/\/codes\/occupations\?q=/, electric]]);
    const onSave = vi.fn().mockResolvedValue(undefined);
    const onClose = vi.fn();
    renderWithProviders(
      <CodeListEditor kind="occupation" current={[]} max={3} onSave={onSave} onClose={onClose} />,
    );

    await userEvent.type(screen.getByLabelText('고용24 직종 찾기'), '전기관리');
    await userEvent.click(await screen.findByRole('button', { name: '아파트 전기관리원' }));
    await userEvent.type(screen.getByLabelText('고용24 직종 찾기'), '경비 반장');
    await userEvent.click(screen.getByRole('button', { name: '‘경비 반장’ 이름만 적기' }));
    await userEvent.click(screen.getByRole('button', { name: '저장' }));

    expect(onSave).toHaveBeenCalledWith([{ code: '834001' }, { name: '경비 반장' }]);
    expect(onClose).toHaveBeenCalled();
  });

  it('지역은 시·도 다음 시·군·구를 골라 더하고, 3개가 차면 더 고를 수 없습니다', async () => {
    mockFetchRoutes([[/\/codes\/regions/, regions]]);
    const onSave = vi.fn().mockResolvedValue(undefined);
    const current = [
      { code: '11500', name: '서울 강서구', status: 'confirmed' as const },
      { code: '11350', name: '서울 노원구', status: 'confirmed' as const },
    ];
    renderWithProviders(
      <CodeListEditor kind="region" current={current} max={3} onSave={onSave} onClose={vi.fn()} />,
    );

    const province = await screen.findByLabelText('시·도');
    await waitFor(() => expect(province).toBeEnabled());
    await userEvent.selectOptions(province, '경기');
    await userEvent.selectOptions(screen.getByLabelText('시·군·구'), '경기 부천시');
    await userEvent.click(screen.getByRole('button', { name: '추가' }));

    expect(screen.queryByLabelText('시·도')).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: '저장' }));
    expect(onSave).toHaveBeenCalledWith([{ code: '11500' }, { code: '11350' }, { code: '41190' }]);
  });

  it('지역은 시·군·구를 고르지 않으면 시·도 전체를 더합니다', async () => {
    mockFetchRoutes([[/\/codes\/regions/, regions]]);
    const onSave = vi.fn().mockResolvedValue(undefined);
    renderWithProviders(
      <CodeListEditor kind="region" current={[]} max={3} onSave={onSave} onClose={vi.fn()} />,
    );

    const province = await screen.findByLabelText('시·도');
    await waitFor(() => expect(province).toBeEnabled());
    await userEvent.selectOptions(province, '경기');
    await userEvent.click(screen.getByRole('button', { name: '추가' }));
    await userEvent.click(screen.getByRole('button', { name: '저장' }));

    expect(onSave).toHaveBeenCalledWith([{ code: '41000' }]);
  });

  it('대화에서 고르기 전인 값은 빼고 다시 골라야 저장되고, 서버 오류는 그대로 보여 줍니다', async () => {
    mockFetchRoutes([[/\/codes\/occupations\?q=/, electric]]);
    const onSave = vi
      .fn()
      .mockRejectedValue(new ApiError('VALIDATION_ERROR', '고용24 목록에 없는 값이에요.', 422));
    const current = [{ code: null, name: '시설관리', status: 'needs_confirmation' as const }];
    renderWithProviders(
      <CodeListEditor
        kind="occupation"
        current={current}
        max={3}
        onSave={onSave}
        onClose={vi.fn()}
      />,
    );

    expect(screen.getByRole('button', { name: '저장' })).toBeDisabled();
    await userEvent.click(screen.getByRole('button', { name: '시설관리 (직종 확인 필요) 빼기' }));
    await userEvent.click(screen.getByRole('button', { name: '저장' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('고용24 목록에 없는 값이에요.');
  });

  it('자격면허는 고용24 자격면허 검색으로 찾고, 목록에 없으면 이름만 적습니다', async () => {
    const fetchMock = mockFetchRoutes([[/\/codes\/licenses\?q=/, { items: [], total: 0 }]]);
    const onSave = vi.fn().mockResolvedValue(undefined);
    renderWithProviders(
      <CodeListEditor kind="license" current={[]} max={1} onSave={onSave} onClose={vi.fn()} />,
    );

    await userEvent.type(screen.getByLabelText('고용24 자격면허 찾기'), '바리스타 2급');
    expect(await screen.findByText('고용24 자격면허 목록에서 찾지 못했어요.')).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: '‘바리스타 2급’ 이름만 적기' }));
    await userEvent.click(screen.getByRole('button', { name: '저장' }));

    expect(String(fetchMock.mock.calls[0][0])).toContain('/codes/licenses?q=');
    expect(onSave).toHaveBeenCalledWith([{ name: '바리스타 2급' }]);
  });
});

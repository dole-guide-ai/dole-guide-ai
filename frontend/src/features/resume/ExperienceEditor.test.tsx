import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import { ExperienceEditor } from '@/features/resume/ExperienceEditor';

const CURRENT = {
  item_id: 'o1',
  experience_type: '경력',
  experience_years: 9,
  experience_months: 2,
  desired_job_description: null,
};

describe('ExperienceEditor', () => {
  it('경력은 연·개월을, 신입은 연·개월 없이 저장합니다', async () => {
    const onSave = vi.fn().mockResolvedValue(undefined);
    render(<ExperienceEditor current={CURRENT} onSave={onSave} onClose={vi.fn()} />);

    const years = screen.getByLabelText('경력 연수');
    await userEvent.clear(years);
    await userEvent.type(years, '10');
    await userEvent.click(screen.getByRole('button', { name: '저장' }));
    expect(onSave).toHaveBeenLastCalledWith('경력', 10, 2);

    await userEvent.selectOptions(screen.getByLabelText('경력여부'), '신입');
    expect(screen.queryByLabelText('경력 연수')).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: '저장' }));
    expect(onSave).toHaveBeenLastCalledWith('신입', null, null);
  });
});

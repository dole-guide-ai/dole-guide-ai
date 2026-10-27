import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import { GpaEditor } from '@/features/resume/GpaEditor';

import { ApiError } from '@/lib/api';

describe('GpaEditor', () => {
  it('총점은 고용24 목록에서 고르고 학점과 함께 저장합니다', async () => {
    const onSave = vi.fn().mockResolvedValue(undefined);
    render(<GpaEditor gpa={null} scale={null} onSave={onSave} onClose={vi.fn()} />);

    expect(screen.getByRole('button', { name: '저장' })).toBeDisabled();
    await userEvent.type(screen.getByLabelText('학점'), '3.8');
    await userEvent.selectOptions(screen.getByLabelText('총점'), '4.5');
    await userEvent.click(screen.getByRole('button', { name: '저장' }));

    expect(onSave).toHaveBeenCalledWith('3.8', '4.5');
  });

  it('만점을 넘으면 서버가 알려 준 이유를 보여 줍니다', async () => {
    const onSave = vi
      .fn()
      .mockRejectedValue(new ApiError('VALIDATION_ERROR', '학점이 4.5점 만점보다 커요.', 422));
    render(<GpaEditor gpa="4.7" scale="4.5" onSave={onSave} onClose={vi.fn()} />);

    await userEvent.click(screen.getByRole('button', { name: '저장' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('학점이 4.5점 만점보다 커요.');
  });
});

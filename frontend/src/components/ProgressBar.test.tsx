import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import { ProgressBar } from '@/components/ProgressBar';

describe('ProgressBar', () => {
  it('현재 단계와 완료 단계를 표시한다', () => {
    render(<ProgressBar current={4} done={[1, 2, 3]} />);

    expect(screen.getByLabelText('실업인정 현재 단계')).toHaveAttribute('aria-current', 'step');
    expect(screen.getByLabelText('구직등록 완료')).toBeInTheDocument();
    expect(screen.getByLabelText('온라인 교육 완료')).toBeInTheDocument();
  });

  it('완료 단계만 눌러서 다시 볼 수 있다', async () => {
    const onStepClick = vi.fn();
    render(<ProgressBar current={2} done={[1]} onStepClick={onStepClick} />);

    await userEvent.click(screen.getByRole('button', { name: '구직등록 단계 다시 보기 (완료)' }));

    expect(onStepClick).toHaveBeenCalledWith(1);
    expect(screen.queryByRole('button', { name: /수급자격 신청/ })).not.toBeInTheDocument();
  });
});

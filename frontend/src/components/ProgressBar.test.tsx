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

  it('다시 보는 단계에 보는 중 표시를 붙이고, 현재 단계를 눌러 돌아갈 수 있다', async () => {
    const onStepClick = vi.fn();
    render(<ProgressBar current={4} done={[1, 2, 3]} viewing={1} onStepClick={onStepClick} />);

    expect(screen.getByLabelText('구직등록 완료 · 보는 중')).toHaveAttribute(
      'aria-current',
      'page',
    );
    expect(screen.getByText('보는 중')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /구직등록/ })).not.toBeInTheDocument();

    await userEvent.click(
      screen.getByRole('button', { name: '실업인정 단계로 돌아가기 (현재 단계)' }),
    );
    expect(onStepClick).toHaveBeenCalledWith(4);
  });

  it('다시 보지 않을 때는 보는 중 표시가 없다', () => {
    render(<ProgressBar current={4} done={[1, 2, 3]} onStepClick={vi.fn()} />);

    expect(screen.queryByText('보는 중')).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /돌아가기/ })).not.toBeInTheDocument();
  });
});

import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import { QuestionCard } from '@/features/chat/QuestionCard';

const CHOICES = ['이력서 만들기 시작할게요', '사진부터 올릴게요', '전체 순서가 궁금해요'];

const renderCard = (isDisabled = false) => {
  const handlers = { onChoice: vi.fn(), onAnswer: vi.fn(), onDismiss: vi.fn() };
  render(<QuestionCard choices={CHOICES} isDisabled={isDisabled} {...handlers} />);
  return handlers;
};

describe('QuestionCard', () => {
  it('고르기만 해서는 보내지 않고, 보내기를 눌러야 고른 선택지를 보낸다', async () => {
    const { onChoice } = renderCard();
    const send = screen.getByRole('button', { name: '고른 답 보내기' });
    expect(send).toBeDisabled();

    await userEvent.click(screen.getByRole('radio', { name: '사진부터 올릴게요' }));
    expect(onChoice).not.toHaveBeenCalled();
    expect(send).toBeEnabled();

    await userEvent.click(send);
    expect(onChoice).toHaveBeenCalledWith('사진부터 올릴게요');
  });

  it('카드 안에서 숫자키로 고를 수 있다', async () => {
    renderCard();

    await userEvent.click(screen.getByRole('radio', { name: '이력서 만들기 시작할게요' }));
    await userEvent.keyboard('3');

    expect(screen.getByRole('radio', { name: '전체 순서가 궁금해요' })).toBeChecked();
  });

  it('직접 답을 적으면 선택이 풀리고, 적은 글을 보낸다', async () => {
    const { onChoice, onAnswer } = renderCard();

    await userEvent.click(screen.getByRole('radio', { name: '사진부터 올릴게요' }));
    await userEvent.type(screen.getByLabelText('직접 답변'), '서류가 없어요{Enter}');

    expect(screen.getByRole('radio', { name: '사진부터 올릴게요' })).not.toBeChecked();
    expect(onAnswer).toHaveBeenCalledWith('서류가 없어요');
    expect(onChoice).not.toHaveBeenCalled();
  });

  it('건너뛰기·닫기는 카드만 닫는다', async () => {
    const { onDismiss, onChoice } = renderCard();

    await userEvent.click(screen.getByRole('button', { name: '건너뛰기' }));
    await userEvent.click(screen.getByRole('button', { name: '질문 닫기' }));

    expect(onDismiss).toHaveBeenCalledTimes(2);
    expect(onChoice).not.toHaveBeenCalled();
  });

  it('답을 만드는 중에는 고를 수 없다', () => {
    renderCard(true);

    expect(screen.getByRole('radio', { name: '사진부터 올릴게요' })).toBeDisabled();
    expect(screen.getByRole('button', { name: '고른 답 보내기' })).toBeDisabled();
  });
});

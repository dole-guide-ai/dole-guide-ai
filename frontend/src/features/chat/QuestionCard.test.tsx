import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import { QuestionCard } from '@/features/chat/QuestionCard';

import { renderWithProviders } from '@/test/renderWithProviders';

const CHOICES = ['이력서 만들기 시작할게요', '사진부터 올릴게요', '전체 순서가 궁금해요'];

const renderCard = (isDisabled = false) => {
  const handlers = { onChoice: vi.fn(), onAnswer: vi.fn(), onDismiss: vi.fn() };
  renderWithProviders(<QuestionCard choices={CHOICES} isDisabled={isDisabled} {...handlers} />);
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

  it('같은 선택지를 한 번 더 누르면 선택이 풀려 보낼 수 없다', async () => {
    const { onChoice } = renderCard();
    const send = screen.getByRole('button', { name: '고른 답 보내기' });

    await userEvent.click(screen.getByRole('radio', { name: '사진부터 올릴게요' }));
    expect(send).toBeEnabled();

    await userEvent.click(screen.getByRole('radio', { name: '사진부터 올릴게요' }));
    expect(send).toBeDisabled();
    expect(onChoice).not.toHaveBeenCalled();
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

  it('질문 문장을 제목으로 보이고, 선택지가 없어도 직접 답을 보낼 수 있다', async () => {
    const handlers = { onChoice: vi.fn(), onAnswer: vi.fn(), onDismiss: vi.fn() };
    renderWithProviders(
      <QuestionCard choices={[]} question="희망 직종은 무엇인가요?" {...handlers} />,
    );

    expect(screen.getByRole('group', { name: '희망 직종은 무엇인가요?' })).toBeInTheDocument();
    expect(screen.queryByRole('radiogroup')).not.toBeInTheDocument();

    await userEvent.type(screen.getByRole('textbox', { name: '직접 답변' }), '창고 관리{Enter}');
    expect(handlers.onAnswer).toHaveBeenCalledWith('창고 관리');
  });

  it('파일 선택지는 고르지 않고 바로 파일 선택창을 열며 말로 보내지 않는다', async () => {
    const handlers = { onChoice: vi.fn(), onAnswer: vi.fn(), onDismiss: vi.fn() };
    const onFileChoice = vi.fn();
    renderWithProviders(
      <QuestionCard
        choices={['이력서 또는 경력증명서 파일 올리기']}
        fileChoice="이력서 또는 경력증명서 파일 올리기"
        onFileChoice={onFileChoice}
        {...handlers}
      />,
    );

    await userEvent.click(
      screen.getByRole('radio', { name: '이력서 또는 경력증명서 파일 올리기' }),
    );

    expect(onFileChoice).toHaveBeenCalledOnce();
    expect(handlers.onChoice).not.toHaveBeenCalled();
    expect(screen.getByRole('button', { name: '고른 답 보내기' })).toBeDisabled();
  });
});

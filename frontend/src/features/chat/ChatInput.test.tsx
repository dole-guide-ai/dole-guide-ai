import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import { ChatInput } from '@/features/chat/ChatInput';

describe('ChatInput', () => {
  it('Enter로 보내고 Shift+Enter는 줄바꿈이다', async () => {
    const onSend = vi.fn();
    const onChange = vi.fn();
    render(<ChatInput value="반장이었어요" onChange={onChange} onSend={onSend} />);

    await userEvent.type(screen.getByLabelText('메시지 입력'), '{Shift>}{Enter}{/Shift}');
    expect(onSend).not.toHaveBeenCalled();

    await userEvent.type(screen.getByLabelText('메시지 입력'), '{Enter}');
    expect(onSend).toHaveBeenCalledWith('반장이었어요');
  });

  it('사진 버튼은 파일 콜백이 있을 때만 켜지고, 고른 파일을 넘긴다', async () => {
    const onFileSelect = vi.fn();
    const { rerender } = render(<ChatInput value="" onChange={vi.fn()} onSend={vi.fn()} />);
    expect(screen.getByRole('button', { name: '사진 올리기' })).toBeDisabled();

    rerender(
      <ChatInput value="" onChange={vi.fn()} onSend={vi.fn()} onFileSelect={onFileSelect} />,
    );
    expect(screen.getByRole('button', { name: '사진 올리기' })).toBeEnabled();

    const file = new File(['합성 이미지'], 'career-cert.png', { type: 'image/png' });
    await userEvent.upload(screen.getByLabelText('사진 파일 선택'), file);

    expect(onFileSelect).toHaveBeenCalledWith(file);
  });

  it('올리는 중에는 사진 버튼 문구가 바뀌고 눌리지 않는다', () => {
    render(
      <ChatInput value="" onChange={vi.fn()} onSend={vi.fn()} onFileSelect={vi.fn()} isUploading />,
    );

    expect(screen.getByRole('button', { name: '사진 올리기' })).toBeDisabled();
    expect(screen.getByRole('button', { name: '사진 올리기' })).toHaveTextContent('올리는 중');
  });
});

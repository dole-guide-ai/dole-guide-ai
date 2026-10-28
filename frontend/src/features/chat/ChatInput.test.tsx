import { render, screen, within } from '@testing-library/react';
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

  it('파일 올리기는 AI가 서류를 요청한 질문에서만 켜지고, 고른 파일을 넘긴다 (시연 개선 2번)', async () => {
    const onFileSelect = vi.fn();
    const { rerender } = render(
      <ChatInput value="" onChange={vi.fn()} onSend={vi.fn()} onFileSelect={onFileSelect} />,
    );
    expect(screen.getByRole('button', { name: '파일 올리기' })).toBeDisabled();
    expect(screen.queryByText(/서류를 올릴 수 있어요/)).not.toBeInTheDocument();

    rerender(
      <ChatInput
        value=""
        onChange={vi.fn()}
        onSend={vi.fn()}
        onFileSelect={onFileSelect}
        isFileRequested
      />,
    );
    expect(screen.getByRole('button', { name: '파일 올리기' })).toBeEnabled();
    expect(screen.getByText(/서류를 올릴 수 있어요/)).toBeInTheDocument();

    const file = new File(['합성 문서'], 'career-cert.pdf', { type: 'application/pdf' });
    await userEvent.upload(screen.getByLabelText('올릴 파일 선택'), file);

    expect(onFileSelect).toHaveBeenCalledWith(file);
  });

  it('올리는 중에는 파일 버튼 문구가 바뀌고 눌리지 않는다', () => {
    render(
      <ChatInput
        value=""
        onChange={vi.fn()}
        onSend={vi.fn()}
        onFileSelect={vi.fn()}
        isFileRequested
        isUploading
      />,
    );

    expect(screen.getByRole('button', { name: '파일 올리기' })).toBeDisabled();
    expect(screen.getByRole('button', { name: '파일 올리기' })).toHaveTextContent('올리는 중');
  });

  it('크게 쓰기 창에서 쓴 글을 보내고 창을 닫는다 (시연 개선 5번)', async () => {
    const onSend = vi.fn();
    render(<ChatInput value="시설관리 반장이었어요" onChange={vi.fn()} onSend={onSend} />);

    await userEvent.click(screen.getByRole('button', { name: '크게 쓰기' }));
    const dialog = screen.getByRole('dialog', { name: '크게 쓰기' });
    expect(screen.getByLabelText('크게 쓰기 입력')).toHaveValue('시설관리 반장이었어요');

    await userEvent.click(screen.getAllByRole('button', { name: '보내기' }).at(-1)!);
    expect(onSend).toHaveBeenCalledWith('시설관리 반장이었어요');
    expect(dialog).not.toBeInTheDocument();
  });

  it('말하기는 누르면 녹음 상태가 되고, 받아쓰는 중에는 눌리지 않으며 실패 안내를 보여 준다', async () => {
    const onVoiceToggle = vi.fn();
    const props = { value: '', onChange: vi.fn(), onSend: vi.fn(), onVoiceToggle };
    const { rerender } = render(<ChatInput {...props} />);

    await userEvent.click(screen.getByRole('button', { name: '눌러서 말하기' }));
    expect(onVoiceToggle).toHaveBeenCalledTimes(1);

    rerender(<ChatInput {...props} voiceStatus="recording" />);
    expect(screen.getByRole('button', { name: '말하기 끝내기' })).toHaveAttribute(
      'aria-pressed',
      'true',
    );
    expect(screen.getByRole('status')).toHaveTextContent('듣고 있어요');

    // 답을 만드는 중(isDisabled)에도 녹음은 끝낼 수 있어야 합니다.
    rerender(<ChatInput {...props} voiceStatus="recording" isDisabled />);
    expect(screen.getByRole('button', { name: '말하기 끝내기' })).toBeEnabled();

    rerender(<ChatInput {...props} voiceStatus="transcribing" />);
    expect(screen.getByRole('button', { name: '눌러서 말하기' })).toBeDisabled();
    expect(screen.getByText('받아쓰는 중…')).toBeInTheDocument();
    expect(screen.getByRole('status')).toHaveTextContent('글로 바꾸고 있어요');

    rerender(<ChatInput {...props} voiceError="마이크를 쓸 수 없어요." />);
    expect(screen.getByRole('alert')).toHaveTextContent('마이크를 쓸 수 없어요.');
  });

  it('녹음·받아쓰는 동안에는 글 입력·크게 쓰기·보내기가 막힌다', () => {
    const props = {
      value: '안녕하세요',
      onChange: vi.fn(),
      onSend: vi.fn(),
      onVoiceToggle: vi.fn(),
    };
    const { rerender } = render(<ChatInput {...props} voiceStatus="recording" />);
    expect(screen.getByRole('textbox', { name: '메시지 입력' })).toBeDisabled();
    expect(screen.getByRole('button', { name: '크게 쓰기' })).toBeDisabled();
    expect(screen.getByRole('button', { name: '보내기' })).toBeDisabled();

    rerender(<ChatInput {...props} voiceStatus="transcribing" />);
    expect(screen.getByRole('textbox', { name: '메시지 입력' })).toBeDisabled();

    rerender(<ChatInput {...props} />);
    expect(screen.getByRole('textbox', { name: '메시지 입력' })).toBeEnabled();
    expect(screen.getByRole('button', { name: '보내기' })).toBeEnabled();
  });

  it('크게 쓰기 창을 연 뒤 녹음이 시작되면 창의 입력과 보내기도 막힌다', async () => {
    const props = {
      value: '안녕하세요',
      onChange: vi.fn(),
      onSend: vi.fn(),
      onVoiceToggle: vi.fn(),
    };
    const { rerender } = render(<ChatInput {...props} />);
    await userEvent.click(screen.getByRole('button', { name: '크게 쓰기' }));

    rerender(<ChatInput {...props} voiceStatus="recording" />);

    const dialog = screen.getByRole('dialog');
    expect(within(dialog).getByRole('textbox', { name: '크게 쓰기 입력' })).toBeDisabled();
    expect(within(dialog).getByRole('button', { name: '보내기' })).toBeDisabled();
  });

  it('말하기 연결이 없으면 버튼이 꺼져 있다', () => {
    render(<ChatInput value="" onChange={vi.fn()} onSend={vi.fn()} />);
    expect(screen.getByRole('button', { name: '눌러서 말하기' })).toBeDisabled();
  });

  it('실업인정 단계에서는 AI 요청이 없어도 증빙을 올릴 수 있고, 강조·안내 문구는 띄우지 않는다', async () => {
    const onFileSelect = vi.fn();
    render(
      <ChatInput
        value=""
        onChange={vi.fn()}
        onSend={vi.fn()}
        onFileSelect={onFileSelect}
        canAttachEvidence
      />,
    );

    const button = screen.getByRole('button', { name: '파일 올리기' });
    expect(button).toBeEnabled();
    expect(button).toHaveAttribute('title', expect.stringContaining('구직활동 증빙'));
    expect(screen.queryByText(/서류를 올릴 수 있어요/)).not.toBeInTheDocument();

    const file = new File(['png'], '지원완료.png', { type: 'image/png' });
    await userEvent.upload(screen.getByLabelText('올릴 파일 선택'), file);
    expect(onFileSelect).toHaveBeenCalledWith(file);
  });
});

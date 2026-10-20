'use client';

import type { KeyboardEvent } from 'react';

import { Button } from '@/components/Button';

/** 입력창 (2-0.4·2-0.5). 글·말·사진 세 가지와 개인정보 안내가 늘 보입니다. 글자 상태는 부모가 가집니다. */
interface ChatInputProps {
  value: string;
  onChange: (value: string) => void;
  onSend: (text: string) => void;
  isDisabled?: boolean;
}

export const ChatInput = ({ value, onChange, onSend, isDisabled = false }: ChatInputProps) => {
  const canSend = !isDisabled && value.trim().length > 0;

  const handleSend = () => {
    if (canSend) onSend(value);
  };

  const handleKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="border-line bg-surface flex flex-col gap-2 border-t p-3">
      <textarea
        value={value}
        onChange={(event) => onChange(event.target.value)}
        onKeyDown={handleKeyDown}
        disabled={isDisabled}
        rows={2}
        placeholder={isDisabled ? '답을 만드는 중이에요…' : '여기에 말씀하듯 적어 주세요'}
        aria-label="메시지 입력"
        className="border-line focus-visible:border-brand focus-visible:ring-brand/40 disabled:bg-neutral-soft w-full resize-none rounded-xl border px-4 py-3 text-base focus-visible:ring-3 focus-visible:outline-hidden"
      />
      <div className="flex flex-wrap items-center gap-2">
        <Button
          variant="secondary"
          size="lg"
          disabled
          title="음성 입력은 서버 음성 인식 경로를 정한 뒤 연결돼요"
          aria-label="눌러서 말하기"
        >
          🎤 말하기
        </Button>
        <Button
          variant="secondary"
          size="lg"
          disabled
          title="사진 올리기는 이력서 단계에서 열려요"
          aria-label="사진 올리기"
        >
          📷 사진
        </Button>
        <Button size="lg" onClick={handleSend} disabled={!canSend} className="ml-auto">
          보내기
        </Button>
      </div>
      <p className="text-muted text-sm">
        개인정보를 입력하지 마세요(데모). 이름·전화번호·주민등록번호는 받지 않아요.
      </p>
    </div>
  );
};

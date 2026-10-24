'use client';

import { type KeyboardEvent, useEffect } from 'react';

import { Button } from '@/components/Button';

/**
 * 크게 쓰기 창 (시연 개선 5번): 입력 글자를 크게 보며 쓰고 보냅니다. 입력창과 같은 글자 상태를 씁니다.
 * Esc나 `닫기`로 닫으면 쓴 글은 입력창에 그대로 남습니다.
 */
interface LargeInputDialogProps {
  value: string;
  onChange: (value: string) => void;
  onSend: (text: string) => void;
  onClose: () => void;
}

export const LargeInputDialog = ({ value, onChange, onSend, onClose }: LargeInputDialogProps) => {
  const canSend = value.trim().length > 0;

  useEffect(() => {
    const handleKey = (event: globalThis.KeyboardEvent) => {
      if (event.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handleKey);
    return () => window.removeEventListener('keydown', handleKey);
  }, [onClose]);

  const handleSend = () => {
    if (!canSend) return;
    onSend(value);
    onClose();
  };

  const handleKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="large-input-title"
        className="bg-surface flex h-[min(85dvh,52rem)] w-full max-w-5xl flex-col gap-4 rounded-3xl p-8 shadow-lg"
      >
        <div className="flex items-center justify-between gap-3">
          <h2 id="large-input-title" className="text-2xl font-bold">
            크게 쓰기
          </h2>
          <Button variant="ghost" onClick={onClose}>
            닫기
          </Button>
        </div>
        <textarea
          value={value}
          onChange={(event) => onChange(event.target.value)}
          onKeyDown={handleKeyDown}
          autoFocus
          placeholder="여기에 말씀하듯 적어 주세요"
          aria-label="크게 쓰기 입력"
          className="border-line focus-visible:border-accent focus-visible:ring-accent/50 min-h-0 w-full flex-1 resize-none rounded-2xl border px-6 py-5 text-3xl leading-relaxed focus-visible:ring-3 focus-visible:outline-hidden"
        />
        <p className="text-muted text-sm">개인정보를 입력하지 마세요(데모).</p>
        <Button size="lg" onClick={handleSend} disabled={!canSend} className="self-end">
          보내기
        </Button>
      </div>
    </div>
  );
};

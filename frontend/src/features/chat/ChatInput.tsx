'use client';

import { type ChangeEvent, type KeyboardEvent, useRef, useState } from 'react';

import { Button } from '@/components/Button';
import { LargeInputDialog } from '@/features/chat/LargeInputDialog';
import { ACCEPTED_FILE_TYPES } from '@/features/chat/useFileUpload';

/** 말하기·파일·크게 쓰기: 아이콘 위·짧은 이름 아래로 작게 둬 입력칸을 넓힙니다 (시연 개선 5번). */
const TOOL_CLASS =
  'focus-visible:ring-brand/40 flex w-16 shrink-0 flex-col items-center gap-0.5 rounded-xl border py-1 text-xs font-semibold focus-visible:ring-3 focus-visible:outline-hidden disabled:cursor-not-allowed';
/** 기본·강조 색은 한쪽만 붙입니다. 둘을 같이 붙이면 배경은 흰색, 글자도 흰색이 돼 이름이 안 보입니다. */
const TOOL_NORMAL =
  'border-line bg-surface text-ink hover:border-brand hover:text-brand disabled:text-muted';
const TOOL_HIGHLIGHT = 'border-brand bg-brand text-white';

/**
 * 입력창 (2-0.4·2-0.5): 입력칸과 말하기·파일 올리기·크게 쓰기·보내기를 한 줄에 둡니다 (시연 개선 5번).
 * 파일 올리기는 AI가 서류를 요청한 질문(`accepts_file`)에서만 켜지고 강조됩니다 (시연 개선 2번).
 * 개인정보 안내는 늘 보입니다. 글자 상태는 부모가 가집니다.
 */
interface ChatInputProps {
  value: string;
  onChange: (value: string) => void;
  onSend: (text: string) => void;
  onFileSelect?: (file: File) => void;
  /** 지금 질문이 서류·사진을 요청했는지 */
  isFileRequested?: boolean;
  isDisabled?: boolean;
  isUploading?: boolean;
}

export const ChatInput = ({
  value,
  onChange,
  onSend,
  onFileSelect,
  isFileRequested = false,
  isDisabled = false,
  isUploading = false,
}: ChatInputProps) => {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [isLargeOpen, setIsLargeOpen] = useState(false);
  const canSend = !isDisabled && value.trim().length > 0;
  const canUpload = !!onFileSelect && isFileRequested && !isDisabled && !isUploading;

  const handleSend = () => {
    if (canSend) onSend(value);
  };

  const handleKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault();
      handleSend();
    }
  };

  const handleFileChange = (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    event.target.value = '';
    if (file && onFileSelect) onFileSelect(file);
  };

  return (
    <div className="border-line bg-surface flex flex-col gap-2 border-t p-3">
      {canUpload && (
        <p className="text-brand text-sm font-semibold">
          서류를 올릴 수 있어요. 사진이나 문서(pdf·hwp·docx) 모두 돼요.
        </p>
      )}
      <div className="flex flex-wrap items-end gap-2 lg:flex-nowrap">
        <textarea
          value={value}
          onChange={(event) => onChange(event.target.value)}
          onKeyDown={handleKeyDown}
          disabled={isDisabled}
          rows={2}
          placeholder={isDisabled ? '답을 만드는 중이에요…' : '여기에 말씀하듯 적어 주세요'}
          aria-label="메시지 입력"
          className="border-line focus-visible:border-brand focus-visible:ring-brand/40 disabled:bg-neutral-soft min-w-32 flex-1 resize-none rounded-xl border px-4 py-3 text-base focus-visible:ring-3 focus-visible:outline-hidden"
        />
        <div className="flex shrink-0 items-center gap-1.5">
          <button
            type="button"
            disabled
            title="음성 입력은 서버 음성 인식 경로를 정한 뒤 연결돼요"
            aria-label="눌러서 말하기"
            className={`${TOOL_CLASS} ${TOOL_NORMAL}`}
          >
            <span aria-hidden className="text-lg">
              🎤
            </span>
            말하기
          </button>
          <input
            ref={fileInputRef}
            type="file"
            accept={ACCEPTED_FILE_TYPES}
            onChange={handleFileChange}
            className="hidden"
            aria-label="올릴 파일 선택"
          />
          <button
            type="button"
            disabled={!canUpload}
            onClick={() => fileInputRef.current?.click()}
            title={
              canUpload
                ? '경력증명서·자격증·예전 이력서·지원 완료 화면 등 사진이나 문서(pdf·hwp·docx)'
                : 'AI가 서류를 요청하면 올릴 수 있어요'
            }
            aria-label="파일 올리기"
            className={`${TOOL_CLASS} ${canUpload ? TOOL_HIGHLIGHT : TOOL_NORMAL}`}
          >
            <span aria-hidden className="text-lg">
              📎
            </span>
            {isUploading ? '올리는 중…' : '파일'}
          </button>
          <button
            type="button"
            disabled={isDisabled}
            onClick={() => setIsLargeOpen(true)}
            aria-label="크게 쓰기"
            className={`${TOOL_CLASS} ${TOOL_NORMAL}`}
          >
            <span aria-hidden className="text-lg">
              🔍
            </span>
            크게 쓰기
          </button>
          <Button size="lg" onClick={handleSend} disabled={!canSend}>
            보내기
          </Button>
        </div>
      </div>
      <p className="text-muted text-sm">
        개인정보를 입력하지 마세요(데모). 이름·전화번호·주민등록번호는 받지 않아요. 올린 파일은 읽은
        뒤 바로 지워요.
      </p>
      {isLargeOpen && (
        <LargeInputDialog
          value={value}
          onChange={onChange}
          onSend={onSend}
          onClose={() => setIsLargeOpen(false)}
        />
      )}
    </div>
  );
};

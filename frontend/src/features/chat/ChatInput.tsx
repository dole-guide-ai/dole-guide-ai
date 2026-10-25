'use client';

import { type ChangeEvent, type KeyboardEvent, useRef, useState } from 'react';

import { ArrowUp, Maximize2, Mic, Paperclip } from 'lucide-react';

import { LargeInputDialog } from '@/features/chat/LargeInputDialog';
import { ACCEPTED_FILE_TYPES } from '@/features/chat/useFileUpload';

import { ICON_SIZE, ICON_STROKE, ICON_STROKE_BOLD } from '@/lib/iconSize';

/** 입력창 안 도구(파일·말하기·크게 쓰기): 아이콘과 짧은 이름을 한 줄로, 누르기 쉽게 높이 44px. */
/** 입력창 안내 문구 id (aria-describedby로 입력칸·파일 버튼에 연결) */
const FILE_HINT_ID = 'chat-file-hint';
const PRIVACY_NOTE_ID = 'chat-privacy-note';

const TOOL_CLASS =
  'focus-visible:ring-brand inline-flex h-11 shrink-0 items-center gap-1.5 rounded-full px-3 text-sm font-semibold transition focus-visible:ring-3 focus-visible:outline-hidden disabled:cursor-not-allowed';
const TOOL_NORMAL =
  'text-ink hover:bg-neutral-soft disabled:text-muted disabled:hover:bg-transparent';
const TOOL_HIGHLIGHT = 'bg-brand-soft text-brand ring-brand/30 ring-1 hover:bg-brand-soft';

/**
 * 입력창 (2-0.4·2-0.5): 글을 쓰는 칸 아래에 도구(파일·말하기·크게 쓰기)와 보내기를 한 상자 안에 둡니다.
 * 파일 올리기는 AI가 서류를 요청한 질문(`accepts_file`)에서만 켜지고 강조됩니다 (시연 개선 2번).
 * 포커스가 들어오면 상자 테두리가 AI 그라데이션으로 바뀝니다. 개인정보 안내는 상자 아래에 늘 보입니다.
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
    <div className="flex flex-col gap-2 px-4 pt-2 pb-3 lg:px-6">
      {canUpload && (
        <p id={FILE_HINT_ID} className="text-brand text-sm font-semibold">
          서류를 올릴 수 있어요. 사진이나 문서(pdf·hwp·docx) 모두 돼요.
        </p>
      )}
      <div className="border-line bg-surface focus-within:border-ai shadow-composer flex flex-col gap-1 rounded-3xl border p-2 transition">
        <textarea
          value={value}
          onChange={(event) => onChange(event.target.value)}
          onKeyDown={handleKeyDown}
          disabled={isDisabled}
          rows={2}
          placeholder={
            isDisabled ? '답을 만드는 중이에요…' : '실업급여에 대해 궁금한 점을 적어 주세요'
          }
          aria-label="메시지 입력"
          aria-describedby={PRIVACY_NOTE_ID}
          className="placeholder:text-muted w-full resize-none bg-transparent px-3 pt-2 text-base leading-relaxed focus-visible:outline-hidden disabled:cursor-not-allowed"
        />
        <div className="flex flex-wrap items-center gap-1">
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
            aria-describedby={canUpload ? FILE_HINT_ID : undefined}
            className={`${TOOL_CLASS} ${canUpload ? TOOL_HIGHLIGHT : TOOL_NORMAL}`}
          >
            <Paperclip aria-hidden size={ICON_SIZE.md} strokeWidth={ICON_STROKE} />
            {isUploading ? '올리는 중…' : '파일'}
          </button>
          <button
            type="button"
            disabled
            title="음성 입력은 서버 음성 인식 경로를 정한 뒤 연결돼요"
            aria-label="눌러서 말하기"
            className={`${TOOL_CLASS} ${TOOL_NORMAL}`}
          >
            <Mic aria-hidden size={ICON_SIZE.md} strokeWidth={ICON_STROKE} />
            말하기
          </button>
          <button
            type="button"
            disabled={isDisabled}
            onClick={() => setIsLargeOpen(true)}
            aria-label="크게 쓰기"
            className={`${TOOL_CLASS} ${TOOL_NORMAL}`}
          >
            <Maximize2 aria-hidden size={ICON_SIZE.md} strokeWidth={ICON_STROKE} />
            크게 쓰기
          </button>
          <button
            type="button"
            onClick={handleSend}
            disabled={!canSend}
            aria-label="보내기"
            className="bg-ai focus-visible:ring-brand disabled:bg-neutral-soft disabled:text-muted ml-auto inline-flex size-11 shrink-0 items-center justify-center rounded-full text-white transition hover:brightness-110 focus-visible:ring-3 focus-visible:outline-hidden disabled:cursor-not-allowed disabled:bg-none"
          >
            <ArrowUp aria-hidden size={ICON_SIZE.lg} strokeWidth={ICON_STROKE_BOLD} />
          </button>
        </div>
      </div>
      <p id={PRIVACY_NOTE_ID} className="text-muted text-center text-sm">
        이름·전화번호·주민등록번호는 적지 마세요. 올린 파일은 읽은 뒤 바로 지워요.
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

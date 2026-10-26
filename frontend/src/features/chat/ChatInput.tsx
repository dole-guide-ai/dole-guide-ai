'use client';

import { type ChangeEvent, type KeyboardEvent, useRef, useState } from 'react';

import { ArrowUp, Maximize2, Mic, Paperclip, Square } from 'lucide-react';

import { LargeInputDialog } from '@/features/chat/LargeInputDialog';
import { ACCEPTED_FILE_TYPES } from '@/features/chat/useFileUpload';
import { VOICE_STATUS, type VoiceStatus } from '@/features/chat/useVoiceInput';

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
const TOOL_RECORDING = 'bg-danger-soft text-danger ring-danger/40 ring-1 animate-pulse';
const VOICE_NOTE_ID = 'chat-voice-note';

const VOICE_LABEL: Record<VoiceStatus, string> = {
  [VOICE_STATUS.IDLE]: '말하기',
  [VOICE_STATUS.RECORDING]: '다 말했어요',
  [VOICE_STATUS.TRANSCRIBING]: '받아쓰는 중…',
};

/**
 * 입력창 (2-0.4·2-0.5): 글을 쓰는 칸 아래에 도구(파일·말하기·크게 쓰기)와 보내기를 한 상자 안에 둡니다.
 * 파일 올리기는 AI가 서류를 요청한 질문(`accepts_file`)에서 켜지고 강조됩니다 (시연 개선 2번).
 * 실업인정 단계처럼 증빙을 언제든 올리는 단계(`canAttachEvidence`)에서는 강조 없이 늘 켜집니다.
 * 포커스가 들어오면 상자 테두리가 AI 그라데이션으로 바뀝니다. 개인정보 안내는 상자 아래에 늘 보입니다.
 */
interface ChatInputProps {
  value: string;
  onChange: (value: string) => void;
  onSend: (text: string) => void;
  onFileSelect?: (file: File) => void;
  /** 지금 질문이 서류·사진을 요청했는지 */
  isFileRequested?: boolean;
  /** 구직활동 증빙을 언제든 올릴 수 있는 단계인지 (실업인정) */
  canAttachEvidence?: boolean;
  isDisabled?: boolean;
  isUploading?: boolean;
  /** 말하기 버튼을 누를 때. 없으면 버튼이 꺼집니다 */
  onVoiceToggle?: () => void;
  voiceStatus?: VoiceStatus;
  /** 말하기 실패 안내 (마이크 거부·인식 실패) */
  voiceError?: string | null;
}

export const ChatInput = ({
  value,
  onChange,
  onSend,
  onFileSelect,
  isFileRequested = false,
  canAttachEvidence = false,
  isDisabled = false,
  isUploading = false,
  onVoiceToggle,
  voiceStatus = VOICE_STATUS.IDLE,
  voiceError = null,
}: ChatInputProps) => {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const isRecording = voiceStatus === VOICE_STATUS.RECORDING;
  const isTranscribing = voiceStatus === VOICE_STATUS.TRANSCRIBING;
  const [isLargeOpen, setIsLargeOpen] = useState(false);
  const canSend = !isDisabled && value.trim().length > 0;
  const canUpload =
    !!onFileSelect && (isFileRequested || canAttachEvidence) && !isDisabled && !isUploading;
  // 강조와 안내 문구는 AI가 서류를 요청했을 때만 (늘 켜진 증빙 버튼은 조용히)
  const isHighlighted = canUpload && isFileRequested;

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
      {isHighlighted && (
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
              isFileRequested
                ? '경력증명서·자격증·예전 이력서·지원 완료 화면 등 사진이나 문서(pdf·hwp·docx)'
                : canAttachEvidence
                  ? '입사지원 완료 화면·면접확인서 같은 구직활동 증빙 사진이나 문서'
                  : 'AI가 서류를 요청하면 올릴 수 있어요'
            }
            aria-label="파일 올리기"
            aria-describedby={isHighlighted ? FILE_HINT_ID : undefined}
            className={`${TOOL_CLASS} ${isHighlighted ? TOOL_HIGHLIGHT : TOOL_NORMAL}`}
          >
            <Paperclip aria-hidden size={ICON_SIZE.md} strokeWidth={ICON_STROKE} />
            {isUploading ? '올리는 중…' : '파일'}
          </button>
          <button
            type="button"
            disabled={!onVoiceToggle || isTranscribing || (isDisabled && !isRecording)}
            onClick={onVoiceToggle}
            aria-label={isRecording ? '말하기 끝내기' : '눌러서 말하기'}
            aria-pressed={isRecording}
            className={`${TOOL_CLASS} ${isRecording ? TOOL_RECORDING : TOOL_NORMAL}`}
          >
            {isRecording ? (
              <Square aria-hidden size={ICON_SIZE.md} strokeWidth={ICON_STROKE} />
            ) : (
              <Mic aria-hidden size={ICON_SIZE.md} strokeWidth={ICON_STROKE} />
            )}
            {VOICE_LABEL[voiceStatus]}
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
      {(isRecording || isTranscribing || voiceError) && (
        <p
          id={VOICE_NOTE_ID}
          role={voiceError ? 'alert' : 'status'}
          className={`text-center text-sm font-semibold ${voiceError ? 'text-danger' : 'text-brand'}`}
        >
          {voiceError ??
            (isRecording
              ? "듣고 있어요. 말씀을 마치면 '다 말했어요'를 눌러 주세요."
              : '말씀을 글로 바꾸고 있어요. 잠시만 기다려 주세요.')}
        </p>
      )}
      <p id={PRIVACY_NOTE_ID} className="text-muted text-center text-sm">
        이름·전화번호·주민등록번호는 적지 마세요. 이력서용 서류는 읽은 뒤 바로 지우고, 구직활동
        증빙은 신청에 쓰도록 보관해요.
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

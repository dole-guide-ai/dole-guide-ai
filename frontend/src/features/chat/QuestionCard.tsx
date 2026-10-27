'use client';

import { type KeyboardEvent, useId, useState } from 'react';

import { CircleHelp, PencilLine, X } from 'lucide-react';

import { Button } from '@/components/Button';

import { ICON_SIZE, ICON_STROKE } from '@/lib/iconSize';

/**
 * 질문 카드 (2-0.4 선택지): 입력창 바로 위에 붙어, 번호 붙은 선택지 중 하나를 고르거나 직접 답을 적은 뒤 `보내기`로 보냅니다.
 * 진입 응답의 `choices`와 `ask_user` 이벤트를 같은 모양으로 처리합니다 (1.11).
 * - 고르기만 해서는 보내지 않습니다(누르기 실수 방지). 숫자키 1·2·3으로도 고를 수 있습니다(카드 안에 포커스가 있을 때).
 * - 직접 답을 적으면 고른 선택지가 풀리고, 글이 그대로 보내집니다.
 * - `건너뛰기`·닫기는 카드만 닫고, 아래 입력창에 자유롭게 적을 수 있습니다.
 */
/** 질문 문장이 없을 때(진입 선택지) 카드 제목 */
const DEFAULT_TITLE = '알맞은 답을 골라 주세요';

interface QuestionCardProps {
  choices: string[];
  /** 카드 제목으로 보일 질문 문장. 없으면(진입 선택지) 기본 문구 */
  question?: string | null;
  onChoice: (choice: string) => void;
  onAnswer: (text: string) => void;
  onDismiss: () => void;
  isDisabled?: boolean;
}

export const QuestionCard = ({
  choices,
  question,
  onChoice,
  onAnswer,
  onDismiss,
  isDisabled = false,
}: QuestionCardProps) => {
  const [selected, setSelected] = useState<string | null>(null);
  const [draft, setDraft] = useState('');
  const titleId = useId();
  const answer = draft.trim();
  const canSend = !isDisabled && (selected !== null || answer.length > 0);

  const handleSend = () => {
    if (!canSend) return;
    if (answer) onAnswer(answer);
    else if (selected) onChoice(selected);
  };

  const select = (choice: string) => {
    setSelected((current) => (current === choice ? null : choice));
    setDraft('');
  };

  // 글 입력칸 밖에서 숫자키를 누르면 그 번호 선택지를 고릅니다.
  const handleKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (isDisabled || (event.target instanceof HTMLInputElement && event.target.type === 'text')) {
      return;
    }
    const index = Number(event.key) - 1;
    if (Number.isInteger(index) && index >= 0 && index < choices.length) {
      event.preventDefault();
      select(choices[index]);
    }
  };

  return (
    <div
      role="group"
      aria-labelledby={titleId}
      onKeyDown={handleKeyDown}
      className="border-line bg-surface shadow-composer flex flex-col gap-3 rounded-3xl border p-4"
    >
      <div className="flex items-center justify-between gap-2">
        <span className="text-muted flex items-center gap-2 text-sm font-semibold">
          <CircleHelp aria-hidden size={ICON_SIZE.md} strokeWidth={ICON_STROKE} />
          질문
        </span>
        <button
          type="button"
          onClick={onDismiss}
          aria-label="질문 닫기"
          className="text-muted hover:bg-neutral-soft hover:text-ink focus-visible:ring-brand inline-flex size-9 items-center justify-center rounded-full focus-visible:ring-3 focus-visible:outline-hidden"
        >
          <X aria-hidden size={ICON_SIZE.md} strokeWidth={ICON_STROKE} />
        </button>
      </div>

      <p id={titleId} className="text-base font-semibold">
        {question ?? DEFAULT_TITLE}
      </p>

      {/* 선택지는 실제 라디오(화살표키로 이동)이고, 화면에는 번호 상자와 글만 보입니다. */}
      {choices.length > 0 && (
        <div role="radiogroup" aria-labelledby={titleId} className="flex flex-col gap-1">
          {choices.map((choice, index) => {
            const isSelected = choice === selected;
            return (
              <label
                key={choice}
                className={`has-focus-visible:ring-brand flex min-h-11 items-center gap-3 rounded-xl px-2 py-1.5 transition has-focus-visible:ring-3 ${isDisabled ? 'cursor-not-allowed' : 'cursor-pointer'} ${isSelected ? 'bg-brand-soft' : 'hover:bg-neutral-soft'}`}
              >
                <input
                  type="radio"
                  name={titleId}
                  value={choice}
                  checked={isSelected}
                  disabled={isDisabled}
                  // 라디오는 이미 고른 것을 다시 눌러도 onChange가 안 나므로 onClick으로 토글합니다.
                  onChange={() => undefined}
                  onClick={() => select(choice)}
                  className="sr-only"
                />
                <span
                  aria-hidden
                  className={`flex size-7 shrink-0 items-center justify-center rounded-md border text-sm font-semibold ${isSelected ? 'border-brand-fill bg-brand-fill text-white' : 'border-line text-muted'}`}
                >
                  {index + 1}
                </span>
                <span
                  className={`text-base ${isSelected ? 'text-brand font-semibold' : 'text-ink'}`}
                >
                  {choice}
                </span>
              </label>
            );
          })}
        </div>
      )}

      <div className="border-line flex flex-wrap items-center gap-2 border-t pt-3">
        <label className="has-focus-visible:ring-brand flex min-w-48 flex-1 items-center gap-2 rounded-lg px-1 has-focus-visible:ring-3">
          <PencilLine
            aria-hidden
            size={ICON_SIZE.md}
            strokeWidth={ICON_STROKE}
            className="text-muted shrink-0"
          />
          <input
            type="text"
            value={draft}
            disabled={isDisabled}
            onChange={(event) => {
              setDraft(event.target.value);
              if (event.target.value.trim()) setSelected(null);
            }}
            onKeyDown={(event) => {
              if (event.key === 'Enter' && !event.nativeEvent.isComposing) handleSend();
            }}
            placeholder={choices.length > 0 ? '또는 직접 답변을 작성하세요' : '답변을 작성하세요'}
            aria-label="직접 답변"
            className="placeholder:text-muted min-w-0 flex-1 bg-transparent py-2 text-base focus-visible:outline-hidden"
          />
        </label>
        <div className="ml-auto flex gap-2">
          <Button variant="secondary" onClick={onDismiss}>
            건너뛰기
          </Button>
          <Button onClick={handleSend} disabled={!canSend} aria-label="고른 답 보내기">
            보내기
          </Button>
        </div>
      </div>
    </div>
  );
};

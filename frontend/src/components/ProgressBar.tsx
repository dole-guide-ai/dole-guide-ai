import { Check } from 'lucide-react';

import { ICON_SIZE, ICON_STROKE_BOLD } from '@/lib/iconSize';
import type { ProgressStep } from '@/types/demo.types';

/** 1.8 진행바. 4단계 고정, 완료 단계는 눌러서 읽기 전용으로 다시 볼 수 있습니다. */
export const PROGRESS_STEPS: { step: ProgressStep; label: string }[] = [
  { step: 1, label: '구직등록' },
  { step: 2, label: '온라인 교육' },
  { step: 3, label: '수급자격 신청' },
  { step: 4, label: '실업인정' },
];

interface ProgressBarProps {
  current: ProgressStep;
  done: ProgressStep[];
  onStepClick?: (step: ProgressStep) => void;
  /** 상단 한 줄에 넣을 때 작게 (시연 개선 4번) */
  isCompact?: boolean;
}

export const ProgressBar = ({
  current,
  done,
  onStepClick,
  isCompact = false,
}: ProgressBarProps) => (
  <ol
    className={`flex flex-wrap items-center ${isCompact ? 'gap-1' : 'gap-2'}`}
    aria-label="절차 진행 단계"
  >
    {PROGRESS_STEPS.map(({ step, label }, index) => {
      const isDone = done.includes(step);
      const isCurrent = step === current;
      const circleClass = isDone
        ? 'bg-ok text-white'
        : isCurrent
          ? 'bg-brand-fill text-white'
          : 'bg-neutral-soft text-muted';
      const labelClass = isCurrent ? 'font-bold text-ink' : isDone ? 'text-ok' : 'text-muted';
      const content = (
        <>
          <span
            className={`flex shrink-0 items-center justify-center rounded-full font-bold ${isCompact ? 'size-6 text-xs' : 'size-8 text-sm'} ${circleClass}`}
            aria-hidden
          >
            {isDone ? <Check size={ICON_SIZE.sm} strokeWidth={ICON_STROKE_BOLD} /> : step}
          </span>
          <span className={`${isCompact ? 'text-sm' : 'text-base'} ${labelClass}`}>{label}</span>
        </>
      );

      return (
        <li key={step} className={`flex items-center ${isCompact ? 'gap-1' : 'gap-2'}`}>
          {index > 0 && (
            <span className={`bg-line h-px ${isCompact ? 'w-2' : 'w-6'}`} aria-hidden />
          )}
          {isDone && onStepClick ? (
            <button
              type="button"
              onClick={() => onStepClick(step)}
              className="hover:bg-ok-soft focus-visible:ring-accent/50 flex items-center gap-2 rounded-lg px-1 py-0.5 focus-visible:ring-3 focus-visible:outline-hidden"
              aria-label={`${label} 단계 다시 보기 (완료)`}
            >
              {content}
            </button>
          ) : (
            <span
              className="flex items-center gap-2 px-1 py-0.5"
              aria-current={isCurrent ? 'step' : undefined}
              aria-label={`${label}${isDone ? ' 완료' : isCurrent ? ' 현재 단계' : ''}`}
            >
              {content}
            </span>
          )}
        </li>
      );
    })}
  </ol>
);

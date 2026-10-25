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

/** 단계 번호 → 이름 (패널 제목 위 `N단계 · 이름` 표시에도 씁니다). */
export const stepLabel = (step: ProgressStep) =>
  PROGRESS_STEPS.find((item) => item.step === step)?.label ?? '';

interface ProgressBarProps {
  current: ProgressStep;
  done: ProgressStep[];
  /** 완료 단계를 누르면 그 단계를, 다시 보는 중에 현재 단계를 누르면 현재 단계를 넘깁니다. */
  onStepClick?: (step: ProgressStep) => void;
  /** 오른쪽 패널에 지금 보이는 단계. 완료 단계를 다시 보는 중이면 그 단계, 아니면 비워 둡니다(= 현재 단계). */
  viewing?: ProgressStep | null;
  /** 상단 한 줄에 넣을 때 작게 (시연 개선 4번) */
  isCompact?: boolean;
}

/**
 * 패널에 보이는 단계는 탭처럼 옅은 파랑 바탕으로 칠하고, 다시 보는 중이면 `보는 중` 표시를 붙입니다.
 * 다시 보는 중에는 현재 단계도 눌러서 돌아갈 수 있습니다.
 */
export const ProgressBar = ({
  current,
  done,
  onStepClick,
  viewing = null,
  isCompact = false,
}: ProgressBarProps) => {
  const isReviewing = viewing !== null && viewing !== current;
  const shown = isReviewing ? viewing : current;

  return (
    <ol
      className={`flex flex-wrap items-center ${isCompact ? 'gap-1' : 'gap-2'}`}
      aria-label="절차 진행 단계"
    >
      {PROGRESS_STEPS.map(({ step, label }, index) => {
        const isDone = done.includes(step);
        const isCurrent = step === current;
        const isShown = step === shown;
        const circleClass = isDone
          ? 'bg-ok text-white'
          : isCurrent
            ? 'bg-brand-fill text-white'
            : 'bg-neutral-soft text-muted';
        const labelClass = isShown
          ? 'font-bold text-brand'
          : isCurrent
            ? 'font-bold text-ink'
            : isDone
              ? 'text-ok'
              : 'text-muted';
        const status = isDone ? '완료' : isCurrent ? '현재 단계' : '';
        const itemClass = `flex items-center gap-2 rounded-lg px-1.5 py-0.5 ${isShown ? 'bg-brand-soft' : ''}`;
        const content = (
          <>
            <span
              className={`flex shrink-0 items-center justify-center rounded-full font-bold ${isCompact ? 'size-6 text-xs' : 'size-8 text-sm'} ${circleClass}`}
              aria-hidden
            >
              {isDone ? <Check size={ICON_SIZE.sm} strokeWidth={ICON_STROKE_BOLD} /> : step}
            </span>
            <span className={`${isCompact ? 'text-sm' : 'text-base'} ${labelClass}`}>{label}</span>
            {isShown && isReviewing && (
              <span className="bg-brand-fill rounded-full px-2 py-0.5 text-xs font-semibold text-white">
                보는 중
              </span>
            )}
          </>
        );
        const isClickable = onStepClick && !isShown && (isDone || (isCurrent && isReviewing));

        return (
          <li key={step} className={`flex items-center ${isCompact ? 'gap-1' : 'gap-2'}`}>
            {index > 0 && (
              <span className={`bg-line h-px ${isCompact ? 'w-2' : 'w-6'}`} aria-hidden />
            )}
            {isClickable ? (
              <button
                type="button"
                onClick={() => onStepClick(step)}
                className={`${itemClass} ${isDone ? 'hover:bg-ok-soft' : 'hover:bg-brand-soft'} focus-visible:ring-brand focus-visible:ring-3 focus-visible:outline-hidden`}
                aria-label={
                  isCurrent
                    ? `${label} 단계로 돌아가기 (현재 단계)`
                    : `${label} 단계 다시 보기 (완료)`
                }
              >
                {content}
              </button>
            ) : (
              <span
                className={itemClass}
                aria-current={isShown && isReviewing ? 'page' : isCurrent ? 'step' : undefined}
                aria-label={`${label}${status ? ` ${status}` : ''}${isShown && isReviewing ? ' · 보는 중' : ''}`}
              >
                {content}
              </span>
            )}
          </li>
        );
      })}
    </ol>
  );
};

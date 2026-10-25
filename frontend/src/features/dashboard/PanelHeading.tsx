import type { LucideIcon } from 'lucide-react';

import { stepLabel } from '@/components/ProgressBar';

import { ICON_SIZE, ICON_STROKE } from '@/lib/iconSize';
import type { ProgressStep } from '@/types/demo.types';

/**
 * 오른쪽 패널 제목. 제목 위에 `N단계 · 단계 이름`을 붙여, 진행바의 어느 단계 화면인지 바로 보이게 합니다.
 * 완료 단계를 다시 볼 때는 `완료` 표시와 `읽기 전용`·`고치는 중` 배지가 붙습니다.
 */
interface PanelHeadingProps {
  icon: LucideIcon;
  name: string;
  step: ProgressStep;
  description?: string;
  isDoneStep?: boolean;
  badge?: string;
}

export const PanelHeading = ({
  icon: Icon,
  name,
  step,
  description,
  isDoneStep = false,
  badge,
}: PanelHeadingProps) => (
  <div className="flex items-start gap-3">
    <span
      aria-hidden
      className="bg-neutral-soft text-ink flex size-11 shrink-0 items-center justify-center rounded-xl"
    >
      <Icon size={ICON_SIZE.lg} strokeWidth={ICON_STROKE} />
    </span>
    <div className="flex min-w-0 flex-col gap-0.5">
      <p className={`text-sm font-semibold ${isDoneStep ? 'text-ok' : 'text-brand'}`}>
        {step}단계 · {stepLabel(step)}
        {isDoneStep && ' · 완료'}
      </p>
      <h2 className="flex flex-wrap items-center gap-2 text-xl leading-tight font-bold">
        {name}
        {badge && (
          <span className="bg-neutral-soft text-neutral rounded-full px-2.5 py-0.5 text-sm font-semibold">
            {badge}
          </span>
        )}
      </h2>
      {description && <p className="text-muted text-base">{description}</p>}
    </div>
  </div>
);

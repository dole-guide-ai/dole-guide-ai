import type { ReactNode } from 'react';

import { CircleCheck } from 'lucide-react';

import { Chip, type ChipTone } from '@/components/Chip';

import { ICON_SIZE, ICON_STROKE_BOLD } from '@/lib/iconSize';

/**
 * 이력서 섹션 (2-1.2): 머리줄에 제목 · 필수/완료 · 설명, 아래에 칸 목록.
 * 박스로 감싸지 않고 섹션 사이 구분선과 여백으로 나눕니다. 완료한 섹션은 제목 앞에 초록 확인 표시가 붙습니다.
 */
interface ResumeSectionProps {
  title: string;
  isRequired?: boolean;
  isDone?: boolean;
  hint?: string;
  /** 섹션 전체 출처를 머리에 한 번만 보일 때 (예: 기본정보 `고용24에서`) */
  badge?: { label: string; tone: ChipTone };
  children: ReactNode;
}

export const ResumeSection = ({
  title,
  isRequired,
  isDone,
  hint,
  badge,
  children,
}: ResumeSectionProps) => (
  <section className="border-line flex flex-col gap-1 border-t pt-6 first-of-type:border-t-0 first-of-type:pt-0">
    <div className="flex flex-wrap items-center gap-2">
      {isDone && (
        <CircleCheck
          aria-hidden
          size={ICON_SIZE.md}
          strokeWidth={ICON_STROKE_BOLD}
          className="text-ok"
        />
      )}
      <h3 className="text-lg font-bold">{title}</h3>
      {isRequired && !isDone && <Chip label="필수" tone="warn" />}
      {isRequired && isDone && <Chip label="완료" tone="ok" />}
      {badge && <Chip label={badge.label} tone={badge.tone} />}
    </div>
    {hint && <p className="text-muted text-sm">{hint}</p>}
    <dl className="divide-line mt-1 divide-y">{children}</dl>
  </section>
);

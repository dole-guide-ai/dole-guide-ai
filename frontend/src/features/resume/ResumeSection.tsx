import type { ReactNode } from 'react';

import { Chip } from '@/components/Chip';

/**
 * 고용24 이력서 영역 하나 (2-1.2). 꼭 묻는 항목이 아직 끝나지 않았으면 `필수` 표시가 남습니다.
 * 도현 실측: 다 입력한 줄 알고 완료를 눌렀다가 빠진 칸 때문에 되돌아가는 일을 막기 위한 표시.
 */
interface ResumeSectionProps {
  title: string;
  /** 꼭 묻는 5개 항목이면 true. 끝나면 ✓, 아니면 `필수`. */
  isRequired?: boolean;
  isDone?: boolean;
  hint?: string;
  children: ReactNode;
}

export const ResumeSection = ({
  title,
  isRequired,
  isDone,
  hint,
  children,
}: ResumeSectionProps) => (
  <section className="border-line border-t pt-3 first:border-t-0 first:pt-0">
    <div className="flex flex-wrap items-center gap-2">
      <h3 className="text-base font-bold">{title}</h3>
      {isRequired && !isDone && <Chip label="필수" tone="warn" />}
      {isRequired && isDone && <Chip label="완료" tone="ok" />}
      {hint && <span className="text-muted text-sm">{hint}</span>}
    </div>
    <dl className="divide-line mt-1 divide-y">{children}</dl>
  </section>
);

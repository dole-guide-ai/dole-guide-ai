import type { ReactNode } from 'react';

import type { LucideIcon } from 'lucide-react';

import { ICON_SIZE, ICON_STROKE } from '@/lib/iconSize';

/**
 * 화면 전체 오류·없는 주소 안내 (error · global-error · not-found 공용).
 * 아이콘 · 제목 · 설명 · 버튼 영역 순서이고, 문의용 오류 번호(`digest`)가 있으면 작게 보여 줍니다.
 */
interface ErrorStateProps {
  icon: LucideIcon;
  title: string;
  description: string;
  actions: ReactNode;
  /** Next가 서버 로그와 맞춰 보도록 붙이는 오류 번호 */
  digest?: string;
}

export const ErrorState = ({
  icon: Icon,
  title,
  description,
  actions,
  digest,
}: ErrorStateProps) => (
  <main className="mx-auto flex min-h-dvh w-full max-w-lg flex-col items-center justify-center gap-5 px-4 py-10 text-center">
    <span
      aria-hidden
      className="bg-neutral-soft text-ink flex size-14 items-center justify-center rounded-2xl"
    >
      <Icon size={ICON_SIZE.lg} strokeWidth={ICON_STROKE} />
    </span>
    <div className="flex flex-col gap-2">
      <h1 className="text-2xl font-bold break-keep">{title}</h1>
      <p className="text-muted text-base break-keep">{description}</p>
    </div>
    <div className="flex flex-wrap justify-center gap-2">{actions}</div>
    {digest && <p className="text-muted text-sm">오류 번호 {digest}</p>}
  </main>
);

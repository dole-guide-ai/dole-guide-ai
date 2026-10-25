import { LoaderCircle } from 'lucide-react';

import { ICON_SIZE, ICON_STROKE } from '@/lib/iconSize';

/**
 * 불러오는 동안 보이는 스피너. 글은 화면 읽기 프로그램에만 읽히고(`sr-only`), 화면에는 도는 아이콘만 보입니다.
 * 움직임을 줄인 환경에서는 돌지 않는 대신 글을 아이콘 옆에 보여 줍니다.
 */
interface SpinnerProps {
  /** 화면 읽기 프로그램이 읽을 글 (예: 이력서를 불러오는 중…) */
  label: string;
  size?: keyof typeof ICON_SIZE;
  /** 패널·화면 가운데에 둘 때 */
  isCentered?: boolean;
}

export const Spinner = ({ label, size = 'lg', isCentered = false }: SpinnerProps) => (
  <div
    role="status"
    className={`text-muted flex items-center ${isCentered ? 'flex-1 justify-center py-10' : 'py-2'}`}
  >
    <LoaderCircle
      aria-hidden
      size={ICON_SIZE[size]}
      strokeWidth={ICON_STROKE}
      className="animate-spin motion-reduce:animate-none"
    />
    {/* 움직임을 줄인 환경에서는 아이콘이 멈추므로 글도 화면에 보입니다. */}
    <span className="sr-only motion-reduce:not-sr-only motion-reduce:ml-2 motion-reduce:text-base">
      {label}
    </span>
  </div>
);

import { LoaderCircle } from 'lucide-react';

import { ICON_SIZE, ICON_STROKE } from '@/lib/iconSize';

/**
 * 불러오는 동안 보이는 스피너. 글은 화면 읽기 프로그램에만 읽히고(`sr-only`), 화면에는 도는 아이콘만 보입니다.
 * 움직임을 줄인 환경에서는 돌지 않습니다.
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
    className={`text-muted flex ${isCentered ? 'flex-1 items-center justify-center py-10' : 'py-2'}`}
  >
    <LoaderCircle
      aria-hidden
      size={ICON_SIZE[size]}
      strokeWidth={ICON_STROKE}
      className="animate-spin motion-reduce:animate-none"
    />
    <span className="sr-only">{label}</span>
  </div>
);

'use client';

import { type KeyboardEvent, type PointerEvent, type RefObject } from 'react';

import { SPLIT_RATIO } from '@/features/dashboard/useSplitRatio';

/**
 * 대화창과 패널 사이 손잡이 (넓은 화면만). 끌거나 방향키로 대화창 폭을 바꾸고, 두 번 누르면 기본 비율로 돌아갑니다.
 * 접근성: `role="separator"`와 현재 값(aria-valuenow)을 둬 스크린리더·키보드로도 조절할 수 있습니다.
 */
interface SplitHandleProps {
  ratio: number;
  onChange: (ratio: number) => void;
  onReset: () => void;
  /** 비율을 잴 기준 영역(대화창·손잡이·패널을 감싼 칸) */
  containerRef: RefObject<HTMLElement | null>;
  controlsId: string;
}

export const SplitHandle = ({
  ratio,
  onChange,
  onReset,
  containerRef,
  controlsId,
}: SplitHandleProps) => {
  const ratioAt = (clientX: number) => {
    const box = containerRef.current?.getBoundingClientRect();
    return box ? ((clientX - box.left) / box.width) * 100 : ratio;
  };

  const handlePointerDown = (event: PointerEvent<HTMLDivElement>) => {
    event.preventDefault();
    event.currentTarget.setPointerCapture(event.pointerId);
  };

  const handlePointerMove = (event: PointerEvent<HTMLDivElement>) => {
    if (event.currentTarget.hasPointerCapture(event.pointerId)) onChange(ratioAt(event.clientX));
  };

  const handleKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    const next = {
      ArrowLeft: ratio - SPLIT_RATIO.step,
      ArrowRight: ratio + SPLIT_RATIO.step,
      Home: SPLIT_RATIO.min,
      End: SPLIT_RATIO.max,
    }[event.key];
    if (next === undefined) return;
    event.preventDefault();
    onChange(next);
  };

  return (
    <div
      role="separator"
      tabIndex={0}
      aria-orientation="vertical"
      aria-label="대화창 폭 조절"
      aria-controls={controlsId}
      aria-valuenow={ratio}
      aria-valuemin={SPLIT_RATIO.min}
      aria-valuemax={SPLIT_RATIO.max}
      aria-valuetext={`대화창 ${ratio}%`}
      title="끌어서 폭 조절 · 두 번 눌러 처음 비율로"
      onPointerDown={handlePointerDown}
      onPointerMove={handlePointerMove}
      onKeyDown={handleKeyDown}
      onDoubleClick={onReset}
      className="group focus-visible:ring-accent/50 bg-line relative hidden w-px cursor-col-resize touch-none items-center justify-center before:absolute before:-inset-x-2 before:inset-y-0 focus-visible:ring-3 focus-visible:outline-hidden lg:flex"
    >
      <span
        aria-hidden
        className="bg-line group-hover:bg-ai group-focus-visible:bg-ai group-active:bg-ai absolute h-12 w-1.5 rounded-full transition-colors"
      />
    </div>
  );
};

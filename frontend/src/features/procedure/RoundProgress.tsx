import type { RoundMarker } from '@/types/procedure.types';

/**
 * 회차 진행 표시 (1.9 ⑤): 받은 회차 ✓, 이번 회차 `!`, 출석 회차 `(출석)`.
 * 총 회차는 소정급여일수에 따라 달라서 표시하지 않고 `…`로 둡니다.
 */
interface RoundProgressProps {
  markers: RoundMarker[];
}

export const RoundProgress = ({ markers }: RoundProgressProps) => (
  <ol className="flex flex-wrap items-center gap-2" aria-label="회차 진행">
    {markers.map(({ round, state, is_attendance }) => {
      const isCurrent = state === 'current';
      return (
        <li
          key={round}
          aria-current={isCurrent ? 'step' : undefined}
          className={`rounded-full px-3 py-1 text-sm font-semibold ${
            isCurrent ? 'bg-warn-soft text-warn' : 'bg-ok-soft text-ok'
          }`}
        >
          {round}차 {isCurrent ? '!' : '✓'}
          {is_attendance && ' (출석)'}
        </li>
      );
    })}
    <li className="text-muted px-1 text-sm" aria-label="이후 회차">
      …
    </li>
  </ol>
);

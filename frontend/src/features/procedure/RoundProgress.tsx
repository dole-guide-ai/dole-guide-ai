import { Check } from 'lucide-react';

import { ICON_SIZE } from '@/lib/iconSize';
import type { RoundMarker } from '@/types/procedure.types';

/**
 * 회차 진행 표시 (1.9 ⑤): 받은 회차 `완료`(초록 확인), 이번 회차 `진행 중`(주황 점), 출석 회차 `(출석)`.
 * 총 회차는 소정급여일수에 따라 달라서 표시하지 않고 `…`로 둡니다.
 */
interface RoundProgressProps {
  markers: RoundMarker[];
}

export const RoundProgress = ({ markers }: RoundProgressProps) => (
  <ol className="flex flex-wrap items-center gap-x-4 gap-y-2" aria-label="회차 진행">
    {markers.map(({ round, state, is_attendance }) => {
      const isCurrent = state === 'current';
      return (
        <li
          key={round}
          aria-current={isCurrent ? 'step' : undefined}
          className={`inline-flex items-center gap-1 text-sm ${
            isCurrent ? 'text-warn font-bold' : 'text-ok font-medium'
          }`}
        >
          {isCurrent ? (
            <span aria-hidden className="bg-warn size-2 rounded-full" />
          ) : (
            <Check aria-hidden size={ICON_SIZE.sm} strokeWidth={2.5} />
          )}
          {round}차 {isCurrent ? '진행 중' : '완료'}
          {is_attendance && ' (출석)'}
        </li>
      );
    })}
    <li className="text-muted px-1 text-sm" aria-label="이후 회차">
      …
    </li>
  </ol>
);

import { CalendarCheck } from 'lucide-react';

import { formatKoreanDate, parseIsoDate } from '@/lib/dateFormat';
import { ICON_SIZE, ICON_STROKE } from '@/lib/iconSize';
import type { DerivedState } from '@/types/demo.types';

/**
 * 패널 B의 수급 종료 예정일·남은 회차 줄 (F-33, 설계 6.6).
 * 종료 예정일은 급여 소진일과 수급기간 끝 중 이른 날이고, 매 회차 인정받는다는 가정이라 실제는 고용센터 확인이 필요합니다.
 */
interface BenefitEndNoteProps {
  derived: DerivedState;
}

export const BenefitEndNote = ({ derived }: BenefitEndNoteProps) => {
  const {
    expected_end_date: endDate,
    remaining_rounds: remaining,
    last_round: lastRound,
  } = derived;
  if (!endDate) return null;
  const isLastRound = lastRound != null && derived.current_round === lastRound;

  return (
    <section aria-label="수급 종료 예정" className="flex items-start gap-2">
      <CalendarCheck
        aria-hidden
        size={ICON_SIZE.md}
        strokeWidth={ICON_STROKE}
        className="text-neutral mt-0.5 shrink-0"
      />
      <div className="flex flex-col gap-1">
        <p className="text-base">
          <span className="font-semibold">수급 종료 예정</span>{' '}
          {parseIsoDate(endDate).getFullYear()}년 {formatKoreanDate(endDate)}
          {remaining != null && ` · 남은 회차 ${remaining}회(이번 회차 포함)`}
        </p>
        {isLastRound && (
          <p className="text-warn text-base font-semibold">
            이번이 마지막 회차예요. 이번 실업인정을 받으면 수급이 끝나요.
          </p>
        )}
        <p className="text-muted text-sm">
          매 회차 인정받는다고 보고 계산했어요. 실제 종료일은 고용센터에서 확인해 주세요.
        </p>
      </div>
    </section>
  );
};

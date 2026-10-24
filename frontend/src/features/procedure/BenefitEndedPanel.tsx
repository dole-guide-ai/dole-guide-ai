import { formatKoreanDate, parseIsoDate } from '@/lib/dateFormat';
import type { DerivedState } from '@/types/demo.types';

/** 수급 종료 화면 (F-33). 종료 뒤에는 활동·신청서를 고칠 수 없어 안내만 보여 줍니다. */
interface BenefitEndedPanelProps {
  derived: DerivedState;
}

const REASON_TEXT = {
  exhausted: '소정급여일수를 모두 받았어요.',
  period_expired: '수급기간(그만둔 다음 날부터 12개월)이 지났어요.',
  employed: '취업해서 수급이 끝났어요.',
} as const;

export const BenefitEndedPanel = ({ derived }: BenefitEndedPanelProps) => {
  const endDate = derived.expected_end_date;

  return (
    <section aria-label="수급 종료" className="flex flex-col gap-3">
      <div className="bg-ok-soft rounded-xl px-4 py-3">
        <p className="text-ok text-lg font-bold">실업급여 수급이 끝났어요</p>
        {endDate && (
          <p className="text-base">
            종료일 {parseIsoDate(endDate).getFullYear()}년 {formatKoreanDate(endDate)}
          </p>
        )}
        {derived.end_reason && <p className="text-base">{REASON_TEXT[derived.end_reason]}</p>}
      </div>
      <p className="text-base">
        지난 활동과 신청서는 진행바에서 다시 볼 수 있지만, 더 고칠 수는 없어요. 다시 일자리를 찾고
        있다면 고용센터에 문의해 주세요.
      </p>
    </section>
  );
};

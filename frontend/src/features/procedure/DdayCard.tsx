import { formatDday, formatDotDate, formatShortDate } from '@/lib/dateFormat';
import type { DerivedState, UserState } from '@/types/demo.types';

/** 패널 B D-day 카드 (시안 1-4 ④): 다음 실업인정일, D-day, 출석 회차 여부, 대상 기간. */
interface DdayCardProps {
  state: UserState;
  derived: DerivedState;
}

export const DdayCard = ({ state, derived }: DdayCardProps) => {
  const { next_recognition_date } = state;
  const { current_round, d_day, is_attendance_round, period } = derived;

  if (!next_recognition_date || current_round === null || d_day === null) return null;

  const isOverdue = d_day < 0;

  return (
    <div className="border-line bg-surface flex flex-col gap-3 rounded-2xl border p-5 shadow-xs">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-muted text-sm">{current_round}차 실업인정일</p>
          <p className="text-2xl font-bold">{formatShortDate(next_recognition_date)}</p>
        </div>
        <span
          className={`rounded-xl px-3 py-2 text-xl font-bold ${
            isOverdue ? 'bg-danger-soft text-danger' : 'bg-brand-soft text-brand'
          }`}
        >
          {formatDday(d_day)}
        </span>
      </div>
      <dl className="grid grid-cols-2 gap-2 text-base">
        <div>
          <dt className="text-muted text-sm">신청 방법</dt>
          <dd className={`font-semibold ${is_attendance_round ? 'text-warn' : 'text-ink'}`}>
            {is_attendance_round ? '고용센터 출석' : '인터넷 신청'}
          </dd>
        </div>
        {period && (
          <div>
            <dt className="text-muted text-sm">대상 기간</dt>
            <dd className="font-semibold">
              {formatDotDate(period.start)} ~ {formatDotDate(period.end)}
            </dd>
          </div>
        )}
      </dl>
    </div>
  );
};

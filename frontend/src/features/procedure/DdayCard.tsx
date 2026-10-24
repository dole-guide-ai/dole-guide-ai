import { Building2, CalendarRange, Monitor } from 'lucide-react';

import { formatDday, formatDotDate, formatShortDate } from '@/lib/dateFormat';
import { ICON_SIZE, ICON_STROKE } from '@/lib/iconSize';
import type { DerivedState, UserState } from '@/types/demo.types';

/** 패널 B 회차 요약 (시안 1-4 ④): 다음 실업인정일 · D-day, 아래에 신청 방법 · 대상 기간. 박스 없이 둡니다. */
interface DdayCardProps {
  state: UserState;
  derived: DerivedState;
}

export const DdayCard = ({ state, derived }: DdayCardProps) => {
  const { next_recognition_date } = state;
  const { current_round, d_day, is_attendance_round, period } = derived;

  if (!next_recognition_date || current_round === null || d_day === null) return null;

  const isOverdue = d_day < 0;
  const MethodIcon = is_attendance_round ? Building2 : Monitor;

  return (
    <section aria-label="이번 회차 일정" className="flex flex-col gap-4">
      <div className="flex items-end justify-between gap-3">
        <div className="flex flex-col gap-1">
          <p className="text-neutral text-sm font-medium">{current_round}차 실업인정일</p>
          <p className="text-3xl leading-none font-bold">
            {formatShortDate(next_recognition_date)}
          </p>
        </div>
        <span
          className={`rounded-full px-4 py-1.5 text-lg font-bold ${
            isOverdue ? 'bg-danger-soft text-danger' : 'bg-brand-soft text-brand'
          }`}
        >
          {formatDday(d_day)}
        </span>
      </div>
      <dl className="grid grid-cols-2 gap-3">
        <div className="flex items-start gap-2">
          <MethodIcon
            aria-hidden
            size={ICON_SIZE.md}
            strokeWidth={ICON_STROKE}
            className="text-neutral mt-0.5 shrink-0"
          />
          <div>
            <dt className="text-neutral text-sm">신청 방법</dt>
            <dd className={`font-semibold ${is_attendance_round ? 'text-warn' : 'text-ink'}`}>
              {is_attendance_round ? '고용센터 출석' : '인터넷 신청'}
            </dd>
          </div>
        </div>
        {period && (
          <div className="flex items-start gap-2">
            <CalendarRange
              aria-hidden
              size={ICON_SIZE.md}
              strokeWidth={ICON_STROKE}
              className="text-neutral mt-0.5 shrink-0"
            />
            <div>
              <dt className="text-neutral text-sm">대상 기간</dt>
              <dd className="font-semibold">
                {formatDotDate(period.start)} ~ {formatDotDate(period.end)}
              </dd>
            </div>
          </div>
        )}
      </dl>
    </section>
  );
};

const DAY_OF_WEEK = ['일', '월', '화', '수', '목', '금', '토'];

/** `YYYY-MM-DD`를 시간대 영향 없이 로컬 날짜로 만듭니다. */
export const parseIsoDate = (iso: string): Date => {
  const [year, month, day] = iso.split('-').map(Number);
  return new Date(year, month - 1, day);
};

const dayOfWeek = (iso: string) => DAY_OF_WEEK[parseIsoDate(iso).getDay()];

const monthDay = (iso: string) => {
  const date = parseIsoDate(iso);
  return { month: date.getMonth() + 1, day: date.getDate() };
};

/** 말풍선용: `12월 22일(화)` (1.7 문구 원칙) */
export const formatKoreanDate = (iso: string): string => {
  const { month, day } = monthDay(iso);
  return `${month}월 ${day}일(${dayOfWeek(iso)})`;
};

/** 상단 문구·카드용: `12.22(화)` */
export const formatShortDate = (iso: string): string => {
  const { month, day } = monthDay(iso);
  return `${month}.${day}(${dayOfWeek(iso)})`;
};

/** 기간 표시용: `11.25` */
export const formatDotDate = (iso: string): string => {
  const { month, day } = monthDay(iso);
  return `${month}.${day}`;
};

/** D-day 표기: 6 → `D-6`, 0 → `D-day`, -2 → `D+2` */
export const formatDday = (days: number): string => {
  if (days === 0) return 'D-day';
  return days > 0 ? `D-${days}` : `D+${Math.abs(days)}`;
};

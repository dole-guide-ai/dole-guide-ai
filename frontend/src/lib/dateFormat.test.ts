import { describe, expect, it } from 'vitest';

import { formatDday, formatDotDate, formatKoreanDate, formatShortDate } from '@/lib/dateFormat';

describe('dateFormat', () => {
  it('말풍선용 날짜를 `12월 22일(화)` 형식으로 만든다', () => {
    expect(formatKoreanDate('2026-12-22')).toBe('12월 22일(화)');
  });

  it('상단 문구용 날짜를 `12.22(화)` 형식으로 만든다', () => {
    expect(formatShortDate('2026-12-22')).toBe('12.22(화)');
    expect(formatDotDate('2026-11-25')).toBe('11.25');
  });

  it('D-day를 남음·당일·지남으로 구분한다', () => {
    expect(formatDday(6)).toBe('D-6');
    expect(formatDday(0)).toBe('D-day');
    expect(formatDday(-3)).toBe('D+3');
  });
});

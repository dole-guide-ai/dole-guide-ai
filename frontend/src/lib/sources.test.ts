import { describe, expect, it } from 'vitest';

import { citeOf, SOURCES } from '@/lib/sources';

const RULE_ID = /\b(?:PROC|ELIG|ACT|DUE|SUP|CHECK|SRC)-\d{3}\b/;

describe('근거 줄 출처 (상세기획 2-0.8)', () => {
  it('출처 여러 개는 `출처명 · 날짜 / 출처명` 한 줄이 된다', () => {
    expect(citeOf('SRC-008', 'SRC-016')).toBe(
      '실업인정 인정기준 · 2026.3.1 신청자부터 / 취업드림수첩(2025년판)',
    );
  });

  it('출처 문구에는 규칙 ID가 들어가지 않는다', () => {
    Object.values(SOURCES).forEach((cite) => expect(cite).not.toMatch(RULE_ID));
  });
});

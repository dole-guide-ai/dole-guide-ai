import { describe, expect, it } from 'vitest';

import { citeOf, SOURCES } from '@/lib/sources';
import { buildMockChatEvents } from '@/mocks/chatScripts';
import { MOCK_ENTRIES } from '@/mocks/entries';

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

  it('모의 대화의 말풍선 글과 근거 줄에 규칙 ID가 보이지 않고, 근거는 출처 목록 이름만 쓴다', () => {
    const allowed = new Set(Object.values(SOURCES));
    const messages = ['안녕하세요', '전체 순서가 궁금해요', '부족한 활동 추천해 주세요'];
    const personas = Object.keys(MOCK_ENTRIES);

    personas.forEach((personaId) =>
      messages.forEach((message) => {
        buildMockChatEvents(personaId, message, []).forEach((event) => {
          if (event.event === 'token') expect(event.data.text).not.toMatch(RULE_ID);
          if (event.event === 'done' && event.data.cite) {
            event.data.cite.split(' / ').forEach((part) => expect(allowed).toContain(part));
          }
        });
      }),
    );
  });
});

import { describe, expect, it } from 'vitest';

import { fieldChip, needsCheck } from '@/lib/fieldChip';

describe('fieldChip', () => {
  it('비어 있으면 아직 없음, 본인 답변 필수 칸은 답변 필요', () => {
    expect(fieldChip(undefined)).toEqual({ label: '아직 없음', tone: 'neutral' });
    expect(fieldChip({ status: 'missing' }, { isSelfAnswerRequired: true })).toEqual({
      label: '답변 필요',
      tone: 'warn',
    });
    expect(fieldChip({ status: 'rejected' }).label).toBe('아직 없음');
  });

  it('바꾼 값과 서로 다른 값은 확인 필요', () => {
    expect(fieldChip({ status: 'extracted', source: 'user_answer', transformed: true })).toEqual({
      label: '확인 필요',
      tone: 'warn',
    });
    expect(fieldChip({ status: 'conflict', source: 'doc' }).label).toBe('확인 필요');
    expect(needsCheck({ status: 'conflict' })).toBe(true);
    expect(needsCheck({ status: 'extracted', source: 'doc' })).toBe(false);
  });

  it('서류·불러오기 값은 파랑, 확정 값은 출처별 초록·회색', () => {
    expect(fieldChip({ status: 'extracted', source: 'doc' }).label).toBe('문서에서 확인');
    expect(fieldChip({ status: 'extracted', source: 'user_answer' }).label).toBe('대화로 추가');
    expect(fieldChip({ status: 'extracted', source: 'seed' }).label).toBe('예전 이력서');
    expect(fieldChip({ status: 'extracted', source: 'work24_import' }).label).toBe(
      '고용24 불러오기',
    );
    expect(fieldChip({ status: 'confirmed', source: 'user_answer' })).toEqual({
      label: '대화로 추가',
      tone: 'ok',
    });
    expect(
      fieldChip({ status: 'confirmed', source: 'user_answer' }, { isSelfAnswerRequired: true })
        .label,
    ).toBe('본인 확인');
    expect(fieldChip({ status: 'confirmed', source: 'direct' }).label).toBe('직접 입력');
    expect(fieldChip({ status: 'confirmed', source: 'auto' })).toEqual({
      label: '자동',
      tone: 'neutral',
    });
    expect(fieldChip({ status: 'not_applicable' }).label).toBe('해당 없음');
  });
});

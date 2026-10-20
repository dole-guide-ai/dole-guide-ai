import { beforeEach, describe, expect, it } from 'vitest';

import { applyFormUpdate, getFormDrafts, resetForms } from '@/lib/formStore';

describe('formStore', () => {
  beforeEach(() => resetForms());

  it('set은 값과 칸 상태(칩 정보)·완성도를 함께 저장한다', () => {
    applyFormUpdate({
      form: 'resume',
      path: 'competencies.careers',
      op: 'append',
      value: { item_id: 'career_001' },
    });
    applyFormUpdate({
      form: 'resume',
      path: 'competencies.careers.career_001.main_duties',
      op: 'set',
      value: '프레스 라인 운영',
      status: 'extracted',
      transformed: true,
      source: 'conversation',
      evidence: { kind: 'utterance', date: '2026-10-12', quote: '작년 3월부터는' },
      completeness: { done: 1, total: 5 },
    });

    const { values, fields, completeness } = getFormDrafts().resume;
    expect(values).toEqual({
      competencies: { careers: [{ item_id: 'career_001', main_duties: '프레스 라인 운영' }] },
    });
    expect(fields['competencies.careers.career_001.main_duties']).toMatchObject({
      status: 'extracted',
      transformed: true,
      source: 'conversation',
    });
    expect(completeness).toEqual({ done: 1, total: 5 });
  });

  it('remove는 값과 칸 상태를 같이 지우고 다른 양식은 건드리지 않는다', () => {
    applyFormUpdate({
      form: 'resume',
      path: 'resume_title',
      op: 'set',
      value: '제목',
      status: 'confirmed',
    });
    applyFormUpdate({ form: 'activities', path: 'items', op: 'append', value: { item_id: 'a1' } });
    applyFormUpdate({ form: 'resume', path: 'resume_title', op: 'remove' });

    expect(getFormDrafts().resume.values).toEqual({});
    expect(getFormDrafts().resume.fields).toEqual({});
    expect(getFormDrafts().activities.values).toEqual({ items: [{ item_id: 'a1' }] });
  });
});

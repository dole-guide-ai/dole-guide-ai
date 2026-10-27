import { beforeEach, describe, expect, it } from 'vitest';

import { applyFormUpdate, getFormDrafts, resetForms, toStoreUpdate } from '@/lib/formStore';

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
      source: 'user_answer',
      evidence: { kind: 'utterance', date: '2026-10-12', quote: '작년 3월부터는' },
      completeness: { filled: 1, total: 5 },
    });

    const { values, fields, completeness } = getFormDrafts().resume;
    expect(values).toEqual({
      competencies: { careers: [{ item_id: 'career_001', main_duties: '프레스 라인 운영' }] },
    });
    expect(fields['competencies.careers.career_001.main_duties']).toMatchObject({
      status: 'extracted',
      transformed: true,
      source: 'user_answer',
    });
    expect(completeness).toEqual({ done: 1, total: 5, sections: {} });
  });

  it('값 없는 set은 값을 두고 칸 상태만 바꾼다 (확인 질문에 "네")', () => {
    applyFormUpdate({
      form: 'resume',
      path: 'resume_title',
      op: 'set',
      value: '제목',
      status: 'extracted',
      transformed: true,
    });
    applyFormUpdate({ form: 'resume', path: 'resume_title', op: 'set', status: 'confirmed' });

    expect(getFormDrafts().resume.values).toEqual({ resume_title: '제목' });
    expect(getFormDrafts().resume.fields.resume_title).toMatchObject({ status: 'confirmed' });
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

describe('toStoreUpdate', () => {
  it('JSON Pointer 경로와 JSON Patch 연산을 저장소 형식으로 바꾼다', () => {
    expect(toStoreUpdate('/careers/-', 'add')).toEqual({ path: 'careers', op: 'append' });
    expect(toStoreUpdate('/job_preferences/hope_wage', 'replace')).toEqual({
      path: 'job_preferences.hope_wage',
      op: 'set',
    });
    expect(toStoreUpdate('/careers/0', 'remove')).toEqual({ path: 'careers.0', op: 'remove' });
  });

  it('점 경로와 예전 연산은 그대로 둔다', () => {
    expect(toStoreUpdate('careers', 'append')).toEqual({ path: 'careers', op: 'append' });
    expect(toStoreUpdate('hope_wage', 'set')).toEqual({ path: 'hope_wage', op: 'set' });
  });
});

it('이벤트의 완성도 {filled, total, sections}를 패널 모양 {done, total, sections}로 바꿔 둔다', () => {
  resetForms();
  applyFormUpdate({
    form: 'resume',
    path: '/resume_title',
    op: 'replace',
    value: '물류 경력 이력서',
    status: 'confirmed',
    completeness: { filled: 2, total: 5, sections: { resume_title: true } },
  });
  expect(getFormDrafts().resume.completeness).toEqual({
    done: 2,
    total: 5,
    sections: { resume_title: true },
  });
});

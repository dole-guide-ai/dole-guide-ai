import { describe, expect, it } from 'vitest';

import { appendPath, getPath, removePath, setPath } from '@/lib/objectPath';

const draft = {
  resume_title: null,
  competencies: {
    careers: [
      { item_id: 'career_001', company_name: 'OO산업', position: null },
      { item_id: 'career_002', company_name: 'OO빌딩', position: '반장' },
    ],
  },
};

describe('objectPath', () => {
  it('점 경로로 값을 읽고, 배열은 item_id로 찾는다', () => {
    expect(getPath(draft, 'competencies.careers.career_002.position')).toBe('반장');
    expect(getPath(draft, 'competencies.careers.1.company_name')).toBe('OO빌딩');
    expect(getPath(draft, 'competencies.careers.none.position')).toBeUndefined();
  });

  it('set은 원본을 두고 바뀐 경로만 새로 만든다', () => {
    const next = setPath(draft, 'competencies.careers.career_001.position', '반장');

    expect(getPath(next, 'competencies.careers.career_001.position')).toBe('반장');
    expect(getPath(draft, 'competencies.careers.career_001.position')).toBeNull();
    expect(next.competencies.careers[1]).toBe(draft.competencies.careers[1]);
  });

  it('없는 중간 경로는 객체로 만들고, 배열에 없는 item_id는 새 항목으로 더한다', () => {
    const next = setPath(draft, 'job_preferences.desired_salary.amount', 250);
    expect(getPath(next, 'job_preferences.desired_salary.amount')).toBe(250);

    const added = setPath(draft, 'competencies.careers.career_003.company_name', 'OO물류');
    expect(getPath(added, 'competencies.careers.career_003')).toEqual({
      item_id: 'career_003',
      company_name: 'OO물류',
    });
  });

  it('append는 배열 끝에 더하고 배열이 없으면 만든다', () => {
    const next = appendPath(draft, 'competencies.certifications', { item_id: 'cert_001' });
    expect(getPath(next, 'competencies.certifications')).toEqual([{ item_id: 'cert_001' }]);
  });

  it('remove는 배열 항목과 객체 키를 지운다', () => {
    const withoutItem = removePath(draft, 'competencies.careers.career_001');
    expect(getPath(withoutItem, 'competencies.careers')).toHaveLength(1);

    const withoutKey = removePath(draft, 'resume_title');
    expect(withoutKey).not.toHaveProperty('resume_title');
  });
});

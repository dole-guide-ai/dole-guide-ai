import { describe, expect, it } from 'vitest';

import { applyFormUpdateToDraft } from '@/lib/formStore';
import { resumeFromServer, resumePatchOp, resumeUpdateFromServer } from '@/lib/resumeForm';
import type { components } from '@/types/api.gen';

type ResumeRead = components['schemas']['ResumeRead'];

const f = (value: unknown, status = 'confirmed', source = 'direct') => ({
  value,
  status,
  source,
  transformed: false,
});
const empty = { value: null, status: 'missing', transformed: false };

const read = {
  status: 'draft',
  lock_version: 3,
  completeness: { filled: 2, total: 5, sections: { resume_title: true, education: true } },
  next_question: 'resume.wish_region',
  can_save: false,
  data: {
    resume_title: f('제조 생산직 이력서'),
    education: [{ item_id: 'e1', education_level: f('고등학교'), school_name: empty }],
    job_preferences: {
      desired_occupations: [
        {
          item_id: 'o1',
          occupation: f({ code: null, name: '프레스 반장', status: 'name_only' }),
          experience_type: f('경력', 'extracted', 'auto'),
          experience_years: f(22),
          experience_months: f(7),
        },
      ],
      desired_regions: f([{ code: null, name: '경기 안성시' }]),
    },
    careers: [{ item_id: 'c1', company_name: f('OO산업', 'conflict', 'doc') }],
    certifications: [],
    certifications_status: f(null, 'not_applicable'),
    competencies: {},
    additional_info: {},
  },
} as unknown as ResumeRead;

describe('resumeFromServer', () => {
  it('새 이력서 구조를 패널의 예전 경로·값으로 바꿉니다', () => {
    const draft = resumeFromServer(read);
    expect(draft.resume_title).toBe('제조 생산직 이력서');
    expect(draft.education[0].level).toBe('고등학교');
    expect(draft.field_states['education.e1.level'].status).toBe('confirmed');
    expect(draft.field_states['education.e1.school_name']).toBeUndefined();
    expect(draft.job_preferences.desired_regions).toEqual(['경기 안성시']);
    expect(draft.job_preferences.desired_occupations[0].name).toBe('프레스 반장');
    expect(draft.job_preferences.experience_summary).toBe('경력 22년 7개월');
    expect(draft.competencies.careers[0].company_name).toBe('OO산업');
    expect(draft.field_states['competencies.careers.c1.company_name'].status).toBe('conflict');
    // 서버 출처 이름을 칩 이름으로: direct → 직접 입력(manual), doc → 문서
    expect(draft.field_states.resume_title.source).toBe('direct');
    expect(draft.field_states['competencies.careers.c1.company_name'].source).toBe('doc');
    expect(draft.field_states['competencies.certifications'].status).toBe('not_applicable');
    expect(draft.completeness).toEqual({
      done: 2,
      total: 5,
      sections: { resume_title: true, education: true },
    });
    expect(draft.lock_version).toBe(3);
  });

  it('경력 기간을 아직 받지 못했으면 경력 구분만 보입니다', () => {
    const data = read.data as unknown as {
      job_preferences: { desired_occupations: Record<string, unknown>[] };
    };
    const occupation = data.job_preferences.desired_occupations[0];
    const noPeriod = {
      ...read,
      data: {
        ...data,
        job_preferences: {
          ...data.job_preferences,
          desired_occupations: [
            { ...occupation, experience_years: f(null), experience_months: f(null) },
          ],
        },
      },
    } as unknown as ResumeRead;

    expect(resumeFromServer(noPeriod).job_preferences.experience_summary).toBe('경력');
  });
});

describe('resumePatchOp', () => {
  it('예전 점 경로를 JSON Patch 경로로 바꿉니다', () => {
    expect(resumePatchOp('competencies.careers.c1.position', '반장')).toEqual({
      op: 'replace',
      path: '/careers/c1/position',
      value: '반장',
    });
    expect(resumePatchOp('education.e1.level', '대학교')?.path).toBe(
      '/education/e1/education_level',
    );
    expect(resumePatchOp('education', [{ item_id: 'edu_001', level: '고등학교' }])).toEqual({
      op: 'replace',
      path: '/education/edu_001/education_level',
      value: '고등학교',
    });
    expect(resumePatchOp('competencies.other_certifications', ['요양보호사'])?.path).toBe(
      '/other_certifications',
    );
    expect(resumePatchOp('job_preferences.experience_summary', '신입')).toBeNull();
  });
});

describe('resumeUpdateFromServer', () => {
  it('대화 중 새 경력 칸을 패널의 경력 목록에 넣습니다', () => {
    const draft = { values: { competencies: { careers: [] } }, fields: {} };
    const update = resumeUpdateFromServer({
      form: 'resume',
      path: '/careers/c1/company_name',
      op: 'add',
      value: '한빛물류',
      status: 'extracted',
    });

    const next = applyFormUpdateToDraft(draft, update);

    expect(next.values).toEqual({
      competencies: { careers: [{ item_id: 'c1', company_name: '한빛물류' }] },
    });
    expect(next.fields['competencies.careers.c1.company_name']?.status).toBe('extracted');
  });

  it('학력 칸 이름과 희망 지역 값을 패널 모양으로 바꿉니다', () => {
    const education = resumeUpdateFromServer({
      form: 'resume',
      path: '/education/e1/education_level',
      op: 'replace',
      value: '고등학교',
    });
    const regions = resumeUpdateFromServer({
      form: 'resume',
      path: '/job_preferences/desired_regions',
      op: 'replace',
      value: [{ name: '인천' }],
    });

    expect(education.path).toBe('/education/e1/level');
    expect(regions.value).toEqual(['인천']);
  });

  it('자격증 없음 상태는 목록을 덮어쓰지 않고 칩만 바꿉니다', () => {
    const update = resumeUpdateFromServer({
      form: 'resume',
      path: '/certifications_status',
      op: 'replace',
      value: 'none',
      status: 'confirmed',
    });

    expect(update).toMatchObject({ path: '/competencies/certifications', value: undefined });
  });
});

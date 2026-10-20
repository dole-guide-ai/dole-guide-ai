import type { ResumeDraftRead } from '@/types/resume.types';

/** 계정별 이력서 초안 스냅샷 (상세기획 2-1.9 구조, 모의값). 박진수는 빈 양식, 최영수는 2019년 예전 이력서. */
const emptyValues = (): Omit<
  ResumeDraftRead,
  'field_states' | 'completeness' | 'next_question' | 'can_save'
> => ({
  schema_version: 'work24_resume_v2',
  status: 'draft',
  resume_title: null,
  education: [],
  job_preferences: {
    desired_occupations: [],
    desired_regions: [],
    desired_salary: { amount: null, unit: null, negotiable: null },
    employment_contract_type: null,
    work_arrangements: [],
    desired_working_hours: null,
    military_alternative: null,
    other_preferences: null,
    search_keywords: [],
  },
  competencies: {
    careers: [],
    certifications: [],
    other_certifications: [],
    projects: [],
    activities_awards: [],
    vocational_training: [],
    computer_skills: { selected_skills: [], other_skills: null },
    languages: [],
    overseas_experiences: [],
    completed_courses: [],
    job_skills: null,
  },
  additional_info: { can_drive: null, owns_vehicle: null },
  enabled_sections: [],
});

const park: ResumeDraftRead = {
  ...emptyValues(),
  field_states: {},
  completeness: { done: 0, total: 5 },
  next_question: 'resume.career_new',
  can_save: false,
};

const OLD = { status: 'extracted', source: 'old_resume' } as const;
const OLD_CHECK = {
  status: 'extracted',
  source: 'old_resume',
  transformed: true,
  evidence: {
    kind: 'old_resume',
    date: '2019-05-10',
    note: '2019년 이력서 값이라 바뀌었을 수 있어요',
  },
} as const;

const choi: ResumeDraftRead = {
  ...emptyValues(),
  resume_title: '시설관리 경력 9년, 성실하게 일하겠습니다',
  education: [
    {
      item_id: 'edu_001',
      level: '고등학교',
      graduation_status: '졸업',
      school_name: 'OO고등학교',
      start_date: '1975-03',
      end_date: '1978-02',
      is_final: true,
    },
  ],
  job_preferences: {
    ...emptyValues().job_preferences,
    desired_occupations: [{ code: null, name: '시설관리', status: 'needs_confirmation' }],
    desired_regions: ['서울 노원구'],
    desired_salary: { amount: 220, unit: 'monthly', negotiable: false },
    employment_contract_type: '기간의 정함이 없는 근로계약',
  },
  competencies: {
    ...emptyValues().competencies,
    careers: [
      {
        item_id: 'career_001',
        company_name: 'OO아파트 관리사무소',
        start_date: '2010-03',
        end_date: '2019-04',
        position: '시설기사',
        employment_status: '퇴직',
        occupation: { code: null, name: '시설관리', status: 'needs_confirmation' },
        main_duties: '전기·설비 점검, 보수 작업',
        monthly_salary: null,
        additional_details: null,
      },
    ],
    certifications: [
      {
        item_id: 'cert_001',
        certificate_name: '전기기능사',
        issuing_organization: '한국산업인력공단',
        acquired_date: '2009-11-20',
      },
    ],
  },
  enabled_sections: ['careers', 'certifications'],
  field_states: {
    resume_title: OLD,
    'education.edu_001.level': OLD,
    'education.edu_001.school_name': OLD,
    'education.edu_001.graduation_status': OLD,
    'job_preferences.desired_occupations': OLD_CHECK,
    'job_preferences.desired_regions': OLD_CHECK,
    'job_preferences.desired_salary': OLD_CHECK,
    'job_preferences.employment_contract_type': OLD_CHECK,
    'competencies.careers': {
      status: 'extracted',
      source: 'old_resume',
      transformed: true,
      evidence: { kind: 'old_resume', date: '2019-05-10', note: '2019년 이후 경력이 비어 있어요' },
    },
    'competencies.careers.career_001.company_name': OLD,
    'competencies.careers.career_001.start_date': OLD,
    'competencies.careers.career_001.end_date': OLD,
    'competencies.careers.career_001.position': OLD,
    'competencies.careers.career_001.employment_status': {
      status: 'confirmed',
      source: 'computed',
    },
    'competencies.careers.career_001.main_duties': OLD,
    'competencies.certifications.cert_001.certificate_name': OLD,
    'competencies.certifications.cert_001.acquired_date': OLD,
  },
  completeness: { done: 3, total: 5 },
  next_question: 'resume.career_since_old',
  can_save: false,
};

const SAVED = { status: 'confirmed', source: 'conversation' } as const;

/** 이정호는 구직등록을 마친 계정이라 저장된(`finalized`) 이력서를 둡니다. 완료 단계 다시 보기(1.8)에 씁니다. */
const lee: ResumeDraftRead = {
  ...emptyValues(),
  status: 'finalized',
  resume_title: '일반 사무 · 행정지원 경력 이력서',
  education: [
    {
      item_id: 'edu_001',
      level: '고등학교',
      graduation_status: '졸업',
      school_name: 'OO고등학교',
      start_date: '1984-03',
      end_date: '1987-02',
      is_final: true,
    },
  ],
  job_preferences: {
    ...emptyValues().job_preferences,
    desired_occupations: [{ code: null, name: '일반 사무', status: 'confirmed' }],
    desired_regions: ['서울 강서구'],
    desired_salary: { amount: 250, unit: 'monthly', negotiable: false },
    employment_contract_type: '기간의 정함이 없는 근로계약',
    military_alternative: '해당 없음',
  },
  competencies: {
    ...emptyValues().competencies,
    careers: [
      {
        item_id: 'career_001',
        company_name: 'OO유통',
        start_date: '2001-04',
        end_date: '2026-08',
        position: '과장',
        employment_status: '퇴직',
        occupation: { code: null, name: '일반 사무', status: 'confirmed' },
        main_duties: '거래처 서류 관리, 사내 행정 지원',
        monthly_salary: null,
        additional_details: null,
      },
    ],
    certifications: [
      {
        item_id: 'cert_001',
        certificate_name: '워드프로세서',
        issuing_organization: '대한상공회의소',
        acquired_date: '2003-06-13',
      },
    ],
  },
  enabled_sections: ['careers', 'certifications'],
  field_states: {
    resume_title: SAVED,
    'education.edu_001.school_name': SAVED,
    'job_preferences.desired_occupations': SAVED,
    'job_preferences.desired_regions': SAVED,
    'job_preferences.desired_salary': SAVED,
    'job_preferences.employment_contract_type': SAVED,
    'job_preferences.military_alternative': SAVED,
    'competencies.careers.career_001.company_name': SAVED,
    'competencies.careers.career_001.end_date': SAVED,
    'competencies.careers.career_001.position': SAVED,
    'competencies.careers.career_001.employment_status': {
      status: 'confirmed',
      source: 'computed',
    },
    'competencies.careers.career_001.main_duties': SAVED,
    'competencies.certifications.cert_001.certificate_name': SAVED,
  },
  completeness: { done: 5, total: 5 },
  next_question: null,
  can_save: false,
};

export const MOCK_RESUMES: Record<string, ResumeDraftRead> = { park, choi, lee };

import type { components } from '@/types/api.gen';
import type { Completeness, FieldEvidence, FieldSource, FieldStatus } from '@/types/chat.types';

/**
 * 이력서 초안 (상세기획 2-1.9 · 데이터 설계 `work24_resume_v2`). `basic_info`는 만들지 않습니다 (2-0.5).
 * 백엔드 API가 올라오면 `api.gen.ts` 타입으로 바꿉니다.
 */

/** 고용24 공통코드 확정 상태 (백엔드 `CodeStatus`). 판정은 서버가 하고 화면은 보여 주기만 합니다. */
export type CodeStatus = 'confirmed' | 'needs_confirmation' | 'name_only';

/** 희망 직종·지역 같은 공통코드 칸 값. `name`은 고른 공식 이름, `said`는 사용자가 말한 이름 */
export interface CodeRef {
  code: string | null;
  name: string;
  status?: CodeStatus;
  said?: string;
}

export interface ResumeEducation {
  item_id: string;
  level: string | null;
  graduation_status: string | null;
  school_name: string | null;
  start_date: string | null;
  end_date: string | null;
  major?: string | null;
  gpa?: string | null;
  /** 총점(만점). 고용24 드롭다운 값(4.0·4.3·4.5·5.0·100) */
  gpa_scale?: string | null;
  /** 고용24 전공코드 (이름은 major) */
  major_code?: CodeRef | null;
  is_final?: boolean;
}

export interface DesiredSalary {
  amount: number | null;
  unit: 'monthly' | null;
  negotiable: boolean | null;
}

/** 패널이 직접 고치는 첫 희망 직종의 경력여부 칸 (경력여부 줄은 첫 직종 기준) */
export interface FirstOccupation {
  item_id: string;
  experience_type: string | null;
  experience_years: number | null;
  experience_months: number | null;
  desired_job_description: string | null;
}

/** 직접 입력에서 고른 공통코드 칸 값. 코드표 이름·상태는 서버가 정합니다(`{name}`은 이름만 적기). */
export type CodeChoice = { code: string } | { name: string };

export interface JobPreferences {
  desired_occupations: CodeRef[];
  first_occupation?: FirstOccupation | null;
  experience_summary?: string | null;
  desired_duties?: string | null;
  desired_regions: CodeRef[];
  desired_salary: DesiredSalary;
  employment_contract_type: string | null;
  work_arrangements: string[];
  desired_working_hours: string | null;
  military_alternative: string | null;
  other_preferences: string | null;
  search_keywords: string[];
}

export interface ResumeCareer {
  item_id: string;
  company_name: string | null;
  start_date: string | null;
  end_date: string | null;
  position: string | null;
  employment_status: string | null;
  occupation: CodeRef | null;
  main_duties: string | null;
  monthly_salary: number | null;
  additional_details: string | null;
}

export interface ResumeCertification {
  item_id: string;
  certificate_name: string | null;
  /** 고용24 자격면허코드 (이름은 certificate_name) */
  certificate_code?: CodeRef | null;
  issuing_organization: string | null;
  acquired_date: string | null;
}

export interface ResumeCompetencies {
  careers: ResumeCareer[];
  certifications: ResumeCertification[];
  other_certifications: string[];
  projects: unknown[];
  activities_awards: unknown[];
  vocational_training: unknown[];
  computer_skills: { selected_skills: string[]; other_skills: string | null };
  languages: unknown[];
  overseas_experiences: unknown[];
  completed_courses: unknown[];
  job_skills: unknown | null;
}

export interface ResumeValues {
  schema_version: string;
  status: 'draft' | 'review' | 'finalized';
  resume_title: string | null;
  education: ResumeEducation[];
  job_preferences: JobPreferences;
  competencies: ResumeCompetencies;
  additional_info: { can_drive: boolean | null; owns_vehicle: boolean | null };
  enabled_sections: string[];
}

export interface ResumeFieldState {
  status: FieldStatus;
  source?: FieldSource;
  transformed?: boolean;
  evidence?: FieldEvidence;
}

/** GET /forms/resume 응답 */
export interface ResumeDraftRead extends ResumeValues {
  field_states: Record<string, ResumeFieldState>;
  completeness: Completeness;
  /** 고용24에 꼭 넣을 칸의 서버 경로(`/education/e1/major`). 판정은 서버가 합니다. */
  required_paths: string[];
  next_question: string | null;
  /** 남은 질문 순서 (2-1.3). 패널의 "AI가 물어볼 순서" 미리 보기에 씁니다. */
  question_queue?: string[];
  can_save: boolean;
  /** 실제 서버 이력서 버전 (PATCH If-Match). 모의 세션에는 없습니다. */
  lock_version?: number;
  /** 이력서 맨 위 기본정보. 고용24 회원정보에서 연동되는 칸이라 고칠 수 없습니다 (F-32). */
  profile_display?: ProfileDisplay | null;
}

/** 기본정보 표시값. 계좌는 끝 4자리만 옵니다. 백엔드 `ProfileDisplay`와 같은 모양입니다. */
export type ProfileDisplay = components['schemas']['ProfileDisplay'];

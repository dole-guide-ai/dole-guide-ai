import type { Completeness, FieldEvidence, FieldSource, FieldStatus } from '@/types/chat.types';

/**
 * 이력서 초안 (상세기획 2-1.9 · 데이터 설계 `work24_resume_v2`). `basic_info`는 만들지 않습니다 (2-0.5).
 * 백엔드 API가 올라오면 `api.gen.ts` 타입으로 바꿉니다.
 */

export interface OccupationRef {
  code: string | null;
  name: string;
  status?: 'confirmed' | 'needs_confirmation' | 'name_only';
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
  is_final?: boolean;
}

export interface DesiredSalary {
  amount: number | null;
  unit: 'monthly' | null;
  negotiable: boolean | null;
}

export interface JobPreferences {
  desired_occupations: OccupationRef[];
  experience_summary?: string | null;
  desired_duties?: string | null;
  desired_regions: string[];
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
  occupation: OccupationRef | null;
  main_duties: string | null;
  monthly_salary: number | null;
  additional_details: string | null;
}

export interface ResumeCertification {
  item_id: string;
  certificate_name: string | null;
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
  next_question: string | null;
  can_save: boolean;
}

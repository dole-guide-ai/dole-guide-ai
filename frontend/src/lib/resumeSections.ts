/** 서버가 완료를 판정하는 꼭 채울 이력서 항목 (백엔드 rules/resume/check.REQUIRED_SECTIONS) */
export const REQUIRED_SECTION = {
  TITLE: 'resume_title',
  EDUCATION: 'education',
  PREFERENCES: 'job_preferences',
  CAREERS: 'careers',
  CERTIFICATIONS: 'certifications',
} as const;
export type RequiredSection = (typeof REQUIRED_SECTION)[keyof typeof REQUIRED_SECTION];

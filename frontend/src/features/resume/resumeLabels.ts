import type { OccupationRef, ResumeEducation } from '@/types/resume.types';

/** `next_question` ID → 패널에 보여 줄 "AI가 물어볼 것" 문구 (상세기획 2-1.3 질문 19개 + 근무 기간). */
export const QUESTION_LABEL: Record<string, string> = {
  'resume.doc_retry': '서류 다시 올리기',
  'resume.value_confirm': '바꾼 값 확인',
  'resume.career_new': '가장 최근에 일하신 곳',
  'resume.career_since_old': '예전 이력서 이후 경력',
  'resume.career_period': '근무 기간',
  'resume.career_duties': '주로 하신 일',
  'resume.career_position': '직급·직책',
  'resume.career_end_check': '마지막 회사 뒤 경력 확인',
  'resume.license': '자격증·면허',
  'resume.license_name': '자격증·면허 이름',
  'resume.career_prev': '그 전 회사',
  'resume.career_later': '그 뒤 회사',
  'resume.optional_detail': '보유 역량 내용',
  'resume.education_level': '학력',
  'resume.education_kind': '대학 종류(2/3년제·4년제)',
  'resume.education_school': '학교 이름·졸업 여부',
  'resume.education_period': '입학·졸업 연도',
  'resume.education_major': '전공',
  'resume.education_gpa': '학점(선택)',
  'resume.wish_job': '하고 싶은 일(희망 직종)',
  'resume.wish_experience': '희망 직종 경력 합계 확인',
  'resume.wish_region': '희망 근무지역',
  'resume.wish_wage': '희망 월급',
  'resume.wish_employment': '고용형태',
  'resume.wish_military': '병역대체 근무 희망 확인',
  'resume.resume_title': '이력서 제목',
  'resume.optional_sections': '그 밖의 보유역량',
  'resume.save_ready': '저장 확인',
  'resume.save_after_fill': '미룬 칸 채우고 저장',
};

/** `YYYY-MM` → `YYYY.MM`, `YYYY-MM-DD` → `YYYY.MM.DD` */
export const formatYm = (value: string | null | undefined) =>
  value ? value.replaceAll('-', '.') : null;

export const formatPeriod = (start: string | null | undefined, end: string | null | undefined) => {
  if (!start && !end) return null;
  return `${formatYm(start) ?? '?'} ~ ${formatYm(end) ?? '?'}`;
};

/**
 * 직종 이름 + 코드 확정 여부. 공통코드로 확정되지 않은 직종(데이터 설계 7.7 `needs_confirmation`)은
 * 확정 코드처럼 보이지 않게 뒤에 표시를 붙입니다.
 */
export const occupationText = (occupation: OccupationRef | null | undefined) => {
  if (!occupation) return null;
  if (occupation.status === 'needs_confirmation') return `${occupation.name} (직종 확인 필요)`;
  if (occupation.status === 'name_only') return `${occupation.name} (고용24에서 직종 선택)`;
  return occupation.name;
};

/** 대학 이상이면 학점/총점·전공을 받습니다 (2-1.2). */
export const isCollegeLevel = (item: ResumeEducation) => !!item.level?.includes('대학');

/**
 * 학점/총점 칸 값 (2-1.2). 대학 이상은 고용24에서 학점/총점이 필수라,
 * 비어 있으면 고용24 입력 때 필요하다고 남깁니다 (2-1.8).
 */
export const gpaText = (item: ResumeEducation) =>
  item.gpa ?? (isCollegeLevel(item) ? '빈칸 (고용24 입력 때 필요)' : null);

/** 고용24 이력서 선택지 (2-1.2 · 데이터 설계 3장). 패널 직접 입력의 선택 상자에 씁니다. */
export const EDUCATION_LEVELS = [
  '무학',
  '초등학교',
  '중학교',
  '고등학교',
  '대학교(2/3년제)',
  '대학교(4년제)',
  '대학원(석사)',
  '대학원(박사)',
] as const;

export const GRADUATION_STATUSES = [
  '휴학',
  '재학',
  '중퇴',
  '수료',
  '졸업',
  '졸업예정',
  '검정(독학)',
] as const;

export const CONTRACT_TYPES = [
  '기간의 정함이 없는 근로계약',
  '기간의 정함이 있는 근로계약',
  '관계없음',
] as const;

export const MILITARY_OPTIONS = [
  '해당 없음',
  '현역병입영대상자',
  '보충역대상자',
  '전문연구요원',
  '산업기능요원',
] as const;

export const EMPLOYMENT_STATUSES = ['퇴직', '재직'] as const;

export const YES_NO = ['예', '아니오'] as const;

/** `2004-03 ~ 2026-09`처럼 적은 기간을 시작·끝으로 나눕니다. 형식 검사는 서버 값 정리가 합니다. */
export const splitPeriod = (text: string) => {
  const [start = '', end = ''] = text.split('~').map((part) => part.trim());
  return { start, end };
};

/** 그 밖의 보유역량 8개 (2-1.2). 값이 들어온 항목만 켜집니다. */
export const OPTIONAL_SECTIONS: { key: string; label: string }[] = [
  { key: 'projects', label: '참여 프로젝트' },
  { key: 'activities_awards', label: '주요활동 및 수상경력' },
  { key: 'vocational_training', label: '직업훈련 이수이력' },
  { key: 'computer_skills', label: '컴퓨터 활용' },
  { key: 'languages', label: '외국어 능력' },
  { key: 'overseas_experiences', label: '해외경험' },
  { key: 'completed_courses', label: '이수 교육 과정' },
];

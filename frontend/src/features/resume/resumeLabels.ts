import type { CodeRef } from '@/types/resume.types';

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
  'resume.wish_job_pick': '희망 직종 고르기(고용24 직종)',
  'resume.wish_job_unmatched': '희망 직종 다시 말하기',
  'resume.wish_region_pick': '희망 근무지역 고르기(고용24 지역)',
  'resume.wish_region_unmatched': '희망 근무지역 다시 말하기',
  'resume.wish_wage': '희망 월급',
  'resume.wish_employment': '고용형태',
  'resume.wish_military': '병역대체 근무 해당 여부',
  'resume.wish_military_kind': '병역대체 근무 종류',
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

/** 공통코드 종류의 화면 이름 */
export const CODE_KIND_LABEL = {
  occupation: '직종',
  region: '지역',
  license: '자격면허',
  major: '전공',
} as const;

/**
 * 공통코드 칸(희망 직종·지역)의 이름 + 확정 여부. 후보를 아직 고르지 않은 값(`needs_confirmation`)과
 * 이름만 적은 값(`name_only`)은 확정 코드처럼 보이지 않게 뒤에 표시를 붙입니다. 상태는 서버가 정합니다.
 */
const codeText = (ref: CodeRef | null | undefined, kind: keyof typeof CODE_KIND_LABEL) => {
  if (!ref) return null;
  const label = CODE_KIND_LABEL[kind];
  if (ref.status === 'needs_confirmation') return `${ref.name} (${label} 확인 필요)`;
  // 고용24 자격면허 목록에 없는 자격은 '기타자격' 칸에 적습니다 (2-1.2).
  if (ref.status === 'name_only')
    return kind === 'license'
      ? `${ref.name} (고용24 기타자격에 적기)`
      : `${ref.name} (고용24에서 ${label} 선택)`;
  return ref.name;
};

export const occupationText = (occupation: CodeRef | null | undefined) =>
  codeText(occupation, 'occupation');

export const regionText = (region: CodeRef | null | undefined) => codeText(region, 'region');

/** 이름 칸 옆 코드 칸(자격면허·전공)이 있으면 그 상태로, 없으면 이름만 보여 줍니다. */
export const namedCodeText = (
  name: string | null | undefined,
  code: CodeRef | null | undefined,
  kind: 'license' | 'major',
) => (code ? codeText(code, kind) : (name ?? null));

/** 고용24 희망 직종·희망 근무지역은 3개까지 (백엔드 rules/resume/check.MAX_PICKS, 서버가 다시 막음) */
export const WORK24_MAX_PICKS = 3;

/** 학점 총점(만점) — 고용24 학력사항 드롭다운 (백엔드 `GpaScale`) */
export const GPA_SCALES = ['4.0', '4.3', '4.5', '5.0', '100'] as const;

/** 희망 직종 경력여부 (백엔드 `ExperienceType`) */
export const EXPERIENCE_TYPES = ['경력', '신입'] as const;

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
export const OPTIONAL_SECTIONS: { key: string; label: string; isImportOnly?: boolean }[] = [
  { key: 'projects', label: '참여 프로젝트' },
  { key: 'activities_awards', label: '주요활동 및 수상경력' },
  { key: 'vocational_training', label: '직업훈련 이수이력' },
  { key: 'computer_skills', label: '컴퓨터 활용' },
  { key: 'languages', label: '외국어 능력' },
  { key: 'overseas_experiences', label: '해외경험' },
  // 이수 교육 과정은 고용24에서 "이력보기"로만 넣어 불러온 값만 보여 줍니다 (2-1.2).
  { key: 'completed_courses', label: '이수 교육 과정', isImportOnly: true },
];

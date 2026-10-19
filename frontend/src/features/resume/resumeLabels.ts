/** `next_question` ID → 패널에 보여 줄 "AI가 물어볼 것" 문구 (상세기획 2-1.3 질문 19개). */
export const QUESTION_LABEL: Record<string, string> = {
  'resume.doc_retry': '서류 다시 올리기',
  'resume.value_confirm': '바꾼 값 확인',
  'resume.career_new': '가장 최근에 일하신 곳',
  'resume.career_since_old': '예전 이력서 이후 경력',
  'resume.career_duties': '주로 하신 일',
  'resume.career_position': '직급·직책',
  'resume.career_end_check': '그만두신 시기 확인',
  'resume.license': '자격증·면허',
  'resume.education_level': '학력',
  'resume.education_detail': '학교 이름·기간',
  'resume.wish_job': '하고 싶은 일(희망 직종)',
  'resume.wish_experience': '희망 직종 경력 합계 확인',
  'resume.wish_region': '희망 근무지역',
  'resume.wish_wage': '희망 월급',
  'resume.wish_employment': '고용형태',
  'resume.wish_military': '병역대체 근무 희망 확인',
  'resume.resume_title': '이력서 제목',
  'resume.optional_sections': '그 밖의 보유역량',
  'resume.save_ready': '저장 확인',
};

/** `YYYY-MM` → `YYYY.MM`, `YYYY-MM-DD` → `YYYY.MM.DD` */
export const formatYm = (value: string | null | undefined) =>
  value ? value.replaceAll('-', '.') : null;

export const formatPeriod = (start: string | null | undefined, end: string | null | undefined) => {
  if (!start && !end) return null;
  return `${formatYm(start) ?? '?'} ~ ${formatYm(end) ?? '?'}`;
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

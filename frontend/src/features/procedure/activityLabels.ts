import type { ChipSpec } from '@/lib/fieldChip';
import type {
  ActivityEvidence,
  ActivityRoute,
  ActivitySource,
  ActivityStatus,
} from '@/types/procedure.types';

/** 활동 행 칩·이름표 (2-2.4 · 2-2.6 · 2-2.9). 계산은 서버 결과(`status`)를 그대로 보여 주기만 합니다. */
export const STATUS_CHIP: Record<ActivityStatus, ChipSpec> = {
  counted: { label: '인정 계산', tone: 'ok' },
  same_day: { label: '같은 날 · 계산 제외', tone: 'neutral' },
  out_of_period: { label: '기간 밖 · 계산 제외', tone: 'neutral' },
  not_allowed: { label: '불인정', tone: 'warn' },
  limit_over: { label: '한도 초과', tone: 'warn' },
  needs_check: { label: '확인 필요', tone: 'warn' },
  planned: { label: '예정', tone: 'info' },
};

export const SOURCE_CHIP: Record<ActivitySource, ChipSpec> = {
  work24_import: { label: '고용24 불러오기 (모의)', tone: 'info' },
  doc: { label: '문서에서 확인', tone: 'info' },
  user_answer: { label: '대화로 추가', tone: 'ok' },
};

export const ROUTE_LABEL: Record<ActivityRoute, string> = {
  work24: '고용24',
  portal: '취업 사이트',
  email: '이메일',
  company_site: '회사 홈페이지',
  newspaper: '신문 공고',
  mail: '우편',
  fax: '팩스',
  visit: '직접 방문',
  referral: '지인 소개',
  interview: '면접',
  job_fair: '채용행사',
  training: '직업훈련',
  center: '고용센터',
  step_online: '온라인 취업특강',
};

export const KIND_LABEL = { job_search: '구직활동', other: '구직 외' } as const;

/** 서버가 활동 종류를 코드(예: job_application)로 줄 때 화면 이름. 모르는 코드는 화면에 영어로 내보내지 않습니다. */
const CATEGORY_LABEL: Record<string, string> = {
  job_application: '입사지원',
  interview: '면접',
  lecture: '취업특강',
  training: '직업훈련',
  counseling: '직업상담',
  job_fair: '채용행사',
};

export const categoryLabel = (category: string) =>
  CATEGORY_LABEL[category] ?? (/^[a-z_]+$/.test(category) ? null : category);

/** 증빙 칩: 필요 증빙이 없으면 `증빙 불필요`, 첨부가 있으면 `증빙 있음`, 아니면 `증빙 필요`(주황). */
export const evidenceChip = (evidence: ActivityEvidence): ChipSpec => {
  if (evidence.required.length === 0) return { label: '증빙 불필요', tone: 'neutral' };
  if (evidence.attached.length > 0) return { label: '증빙 있음', tone: 'ok' };
  return { label: '증빙 필요', tone: 'warn' };
};

/** 패널 B `활동 정리 끝 · 신청서 만들기`를 누르면 대화로 보내는 말 (2-2.9 → 2-3) */
export const OPEN_FORM_MESSAGE = '활동 정리 끝났어요. 신청서 만들어 주세요';

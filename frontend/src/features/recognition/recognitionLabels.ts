import { formatShortDate } from '@/lib/dateFormat';
import type { ChipSpec } from '@/lib/fieldChip';
import type { FieldSource } from '@/types/chat.types';
import type {
  AttendItem,
  ChecklistKey,
  ExcludedActivity,
  SubmitMode,
} from '@/types/recognition.types';

/**
 * 패널 C 화면 문구 (2-3.6 표). 어떤 모드인지·낼 수 있는지는 서버 값(`submit_mode`·`can_submit`)을 그대로 쓰고,
 * 여기서는 모드별 버튼 이름과 안내 문장만 고릅니다.
 */
interface SubmitModeText {
  button: string;
  /** 비활성 모드(17시 이후·인정일 지남)는 버튼을 누를 수 없습니다. */
  isActionable: boolean;
  guide: (recognitionDate: string) => string;
}

export const SUBMIT_MODE_TEXT: Record<SubmitMode, SubmitModeText> = {
  attend: {
    button: '출석 준비 확인 (모의)',
    isActionable: true,
    guide: (date) =>
      `${formatShortDate(date)}은 고용센터에 직접 가는 출석 회차라 인터넷으로 내지 않아요. 신분증과 수급자격증을 챙겨 가세요.`,
  },
  preview: {
    button: '임시저장 (모의)',
    isActionable: true,
    guide: (date) =>
      `지금은 저장만 돼요. 제출은 ${formatShortDate(date)} 0시부터 17시까지만 할 수 있어요. 그날 다시 열어 주세요.`,
  },
  send: {
    button: '확인 후 제출 (모의)',
    isActionable: true,
    guide: () =>
      '보내기 전에 한 번 더 확인해 주세요. 임시저장만으로는 신청이 안 되고, 제출은 본인이 해요.',
  },
  visit_today: {
    button: '인터넷 제출 마감',
    isActionable: false,
    guide: () => '인터넷 제출은 끝났어요. 오늘 18시까지 고용센터에 가서 신청할 수 있어요.',
  },
  change: {
    button: '변경 신청 안내',
    isActionable: false,
    guide: () => '인정일부터 14일 안에 고용센터에 가서 변경 신청을 할 수 있어요(수급기간 중 1회).',
  },
};

export const CHECKLIST_LABEL: Record<ChecklistKey, string> = {
  self_answers: '근로·취업·산재 본인 답변',
  job_search_fields: '구직활동 필수 칸',
  notification: '지급 결정 통지 방법',
  next_activity: '다음 출석일까지 활동',
  unemployment_credit: '실업크레딧 답',
  requirement_met: '필요 활동 충족',
  evidence_ok: '증빙 첨부',
};

export const ATTEND_ITEM_LABEL: Record<AttendItem, string> = {
  id_card: '신분증',
  eligibility_card: '수급자격증',
};

/** 계산에서 뺀 활동의 이유 (2-2.6 계산 결과와 같은 이름). */
export const EXCLUDED_REASON_LABEL: Record<ExcludedActivity['reason'], string> = {
  same_day: '같은 날',
  out_of_period: '기간 밖',
  not_allowed: '불인정',
};

/**
 * 활동 한 건의 증빙 칩. 고용24로 지원한 건(불러오기)은 별도 증빙이 필요 없고(ACT-132),
 * 취업 사이트·이메일·면접 등은 증빙이 있어야 해요(ACT-133~141).
 */
export const activityEvidenceChip = (activity: {
  attachment_ids: string[];
  source: FieldSource;
}): ChipSpec => {
  if (activity.attachment_ids.length > 0) return { label: '증빙 있음', tone: 'ok' };
  if (activity.source === 'work24_import') {
    return { label: '증빙 불필요 (고용24 지원)', tone: 'neutral' };
  }
  return { label: '증빙 필요', tone: 'warn' };
};

/** 예·아니오 본인 답변 표시. null이면 아직 답하지 않음. */
export const yesNo = (value: boolean | null | undefined) =>
  value === null || value === undefined ? null : value ? '있음' : '없음';

/** 모의 제출·출석 준비 확인 뒤 다음 안내(2-3.7)를 이어 가려고 대화로 보내는 말 */
export const CONFIRMED_MESSAGE = {
  attend: '출석 준비 확인했어요',
  send: '신청서 제출했어요',
} as const;

import { formatDday, formatKoreanDate } from '@/lib/dateFormat';
import type { SessionRead } from '@/types/demo.types';

/**
 * 상단 `다음 기한·다음 할 일` 한 줄 (1.8). 백엔드 문구(`next_step_text`)는 `다음 기한 : 4차 실업인정일 10.27(화) · 고용센터 출석`처럼
 * 이름표·날짜·안내가 한 덩어리라, 화면에서는 이름표 · 무엇을(굵게) · D-day · 덧붙임으로 나눠 보여 줍니다.
 * - 실업인정 단계: 세션의 회차·인정일·D-day·출석 여부로 새로 만듭니다.
 * - 그 밖의 단계: 백엔드 문구에서 `다음 할 일 :` 머리말만 떼어 씁니다.
 */
export interface NextStepView {
  label: '다음 기한' | '다음 할 일';
  text: string;
  dday?: string;
  note?: string;
}

const PREFIX = /^\s*다음\s*(기한|할 일)\s*:\s*/;

export const nextStepView = ({ state, derived, entry }: SessionRead): NextStepView | null => {
  const round = derived.current_round;
  const date = state.next_recognition_date;
  if (state.stage === 'recognition' && round && date) {
    return {
      label: '다음 기한',
      text: `${round}차 실업인정일 ${formatKoreanDate(date)}`,
      dday: derived.d_day === null ? undefined : formatDday(derived.d_day),
      note: derived.is_attendance_round ? '고용센터에 직접 가요' : undefined,
    };
  }
  const text = entry.next_step_text.replace(PREFIX, '').trim();
  return text ? { label: '다음 할 일', text } : null;
};

import type { SessionRead, UserState } from '@/types/demo.types';

/**
 * 패널 안 주의 상자를 처음 한 번 토스트로도 알리기 위한 목록 (시연 개선 6번).
 * 조건은 패널이 상자를 보이는 조건과 같고, 값은 세션의 상태·파생값(백엔드 계산)을 그대로 씁니다.
 */
export interface SessionNotice {
  /** 같은 알림을 다시 띄우지 않으려고 쓰는 키 */
  key: string;
  title: string;
  text: string;
}

/** M1 (1.6): 이직 당시 65세 이상이고 수급자격 신청 전 단계면 신청 경로 안내 상자를 둡니다. */
export const showsVisitNotice = (state: UserState) =>
  state.age_at_separation >= 65 &&
  ['job_registration', 'education', 'eligibility_application'].includes(state.stage);

export const sessionNotices = ({ state, derived }: SessionRead): SessionNotice[] => {
  const notices: SessionNotice[] = [];
  if (showsVisitNotice(state)) {
    notices.push({
      key: 'visit',
      title: '신청 경로 안내',
      text: '이직일 기준 만 65세 이상이라 수급자격 신청은 관할 고용센터에 방문해서 해요.',
    });
  }
  if (state.stage === 'recognition' && (derived.d_day ?? 0) < 0) {
    notices.push({
      key: `overdue-${state.next_recognition_date}`,
      title: '실업인정일이 지났어요',
      text: '인정일부터 14일 안에 고용센터에 가서 변경 신청을 할 수 있어요(수급기간 중 1회).',
    });
  } else if (state.stage === 'recognition' && derived.is_attendance_round) {
    notices.push({
      key: `attend-${derived.current_round}`,
      title: `${derived.current_round}차는 고용센터 출석 회차예요`,
      text: '인터넷으로 내지 않고 직접 가요. 신분증과 수급자격증을 챙기세요.',
    });
  }
  return notices;
};

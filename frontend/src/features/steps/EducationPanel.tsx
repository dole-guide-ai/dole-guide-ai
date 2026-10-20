import { EvidenceLine } from '@/components/EvidenceLine';
import { FieldRow } from '@/features/resume/FieldRow';

import type { UserState } from '@/types/demo.types';

/**
 * 패널 E 온라인 교육 (1.6 E6 · 1.8). 대화 과정은 기획 "예정"이라 1.8 표 수준의 정적 화면입니다.
 * 이수 여부는 상태 값(`education_done`)을 그대로 보여 주고, 이수 확인은 대화로 받습니다.
 */
interface EducationPanelProps {
  state: UserState;
  isReadOnly?: boolean;
}

const SOURCE_WORK24 = '고용24 실업급여(상용직)';

export const EducationPanel = ({ state, isReadOnly = false }: EducationPanelProps) => {
  const isVisit = state.age_at_separation >= 65;

  return (
    <div className="flex flex-col gap-4">
      <dl className="divide-line divide-y">
        <FieldRow
          label="교육"
          value="수급자격 신청자 온라인 교육 · 약 1시간"
          chip={{ label: '필수', tone: 'warn' }}
        />
        <FieldRow
          label="듣는 곳"
          value="고용24 실업급여 메뉴의 온라인 교육 (고용센터에서도 들을 수 있어요)"
          chip={{ label: '고용24에서', tone: 'neutral' }}
        />
        <FieldRow
          label="이수 여부"
          value={state.education_done ? '이수 완료' : '아직 이수 전'}
          chip={
            state.education_done
              ? { label: '본인 확인', tone: 'ok' }
              : { label: '확인 필요', tone: 'warn' }
          }
        />
        <FieldRow
          label="다음 할 일"
          value={
            isVisit
              ? '교육 이수 후 관할 고용센터에 방문해 수급자격 신청'
              : '교육 이수 후 수급자격 신청 (인터넷 사전제출 또는 센터 방문)'
          }
          chip={{ label: '자동', tone: 'neutral' }}
        />
      </dl>
      {!isReadOnly && !state.education_done && (
        <p className="bg-brand-soft text-brand rounded-xl px-4 py-3 text-base">
          교육을 다 들으셨으면 대화창에 &ldquo;교육 다 들었어요&rdquo;라고 알려 주세요.
        </p>
      )}
      <EvidenceLine cite={SOURCE_WORK24} />
    </div>
  );
};

import { EvidenceLine } from '@/components/EvidenceLine';
import { FieldRow } from '@/features/resume/FieldRow';

import type { DerivedState, UserState } from '@/types/demo.types';

/**
 * 패널 Q 수급자격 신청 (1.6 E5a · 1.8). 대화 과정은 기획 "예정"이라 정적 화면입니다.
 * 신청 경로는 서버 파생값 `can_presubmit_online`(이직일 기준 만 65세 미만, PROC-048)을 그대로 씁니다.
 */
interface EligibilityPanelProps {
  state: UserState;
  derived: DerivedState;
  isReadOnly?: boolean;
}

const SOURCE = '고용24 실업급여(상용직) · 찾기쉬운 생활법령정보';

export const EligibilityPanel = ({ state, derived, isReadOnly = false }: EligibilityPanelProps) => {
  const isApplied = state.stage === 'eligibility_applied' || state.stage === 'recognition';

  return (
    <div className="flex flex-col gap-4">
      <dl className="divide-line divide-y">
        <FieldRow
          label="신청 경로"
          value={
            derived.can_presubmit_online
              ? '인터넷 사전제출 가능 (그 밖의 제출 요건도 맞아야 해요) 또는 고용센터 방문'
              : '관할 고용센터에 방문해서 신청'
          }
          chip={{ label: '자동', tone: 'neutral' }}
        />
        <FieldRow label="준비물" value="신분증" chip={{ label: '필수', tone: 'warn' }} />
        <FieldRow
          label="미리 확인"
          value="회사의 이직확인서 처리 여부 (고용24에서 조회)"
          chip={{ label: '고용24에서', tone: 'neutral' }}
        />
        <FieldRow
          label="신청 뒤"
          value="고용센터가 1차 실업인정일을 정해 알려 줘요"
          chip={isApplied ? { label: '신청 완료', tone: 'ok' } : { label: '안내', tone: 'neutral' }}
        />
      </dl>
      {state.age_at_separation >= 65 && (
        <p className="bg-warn-soft text-warn rounded-xl px-4 py-3 text-base">
          65세 이후에 새로 고용됐거나 자영업을 시작했다면 실업급여가 적용되지 않을 수 있어요.
          고용센터에 확인해 주세요.
        </p>
      )}
      {!isReadOnly && !isApplied && (
        <p className="text-muted text-sm">
          신청을 마치면 대화창에 알려 주세요. 다음 단계에서 1차 실업인정일을 받아요.
        </p>
      )}
      <EvidenceLine cite={SOURCE} />
    </div>
  );
};

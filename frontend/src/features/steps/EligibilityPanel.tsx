import { EvidenceLine } from '@/components/EvidenceLine';
import { FieldRow } from '@/features/resume/FieldRow';
import { ProcedureFactForm } from '@/features/steps/ProcedureFactForm';

import { citeOf } from '@/lib/sources';
import type { DerivedState, UserState } from '@/types/demo.types';

/**
 * 패널 Q 수급자격 신청 (1.6 E5a · 1.8). 대화 과정은 기획 "예정"이라 정적 화면입니다.
 * 신청 경로는 서버 파생값 `can_presubmit_online`(이직일 기준 만 65세 미만, PROC-048)을 그대로 씁니다.
 */
interface EligibilityPanelProps {
  state: UserState;
  derived: DerivedState;
  /** 있으면 수급자격 신청일 입력을 보입니다 (F-16) */
  personaId?: string;
  isReadOnly?: boolean;
}

const SOURCE = citeOf('SRC-001', 'SRC-011', 'SRC-013');

/** 인터넷 사전제출 조건 (PROC-048). 모두 맞아야 하고, 나이 외에는 서비스가 확인하지 않습니다. */
const PRESUBMIT_CONDITIONS = [
  '회사의 상실신고·이직확인서 처리가 끝났어요',
  '고용보험 가입 기간(피보험단위기간)이 180일 이상이에요',
  '회사 사정 등 본인 뜻이 아닌 이유로 그만뒀어요',
  '그만둔 날 기준 만 65세 미만이에요',
];

export const EligibilityPanel = ({
  state,
  derived,
  personaId,
  isReadOnly = false,
}: EligibilityPanelProps) => {
  const isApplied = state.stage === 'eligibility_applied' || state.stage === 'recognition';

  return (
    <div className="flex flex-col gap-4">
      <dl className="divide-line divide-y">
        <FieldRow
          label="신청 경로"
          value={
            derived.can_presubmit_online
              ? '인터넷 사전제출(아래 조건을 모두 갖췄을 때) 또는 고용센터 방문'
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
      {derived.can_presubmit_online && (
        <section
          className="bg-canvas flex flex-col gap-1 rounded-xl px-4 py-3"
          aria-label="인터넷 사전제출 조건"
        >
          <p className="text-base font-semibold">인터넷 사전제출은 아래를 모두 갖춰야 해요</p>
          <ul className="flex list-disc flex-col gap-0.5 pl-5 text-base">
            {PRESUBMIT_CONDITIONS.map((condition) => (
              <li key={condition}>{condition}</li>
            ))}
          </ul>
          <p className="text-muted text-sm">
            인터넷으로 내도 신청이 끝난 게 아니에요. 그다음 고용센터에 한 번 가야 해요.
          </p>
        </section>
      )}
      <p className="bg-brand-soft text-brand rounded-xl px-4 py-3 text-base">
        실업급여는 그만둔 다음 날부터 12개월 안에서만 받을 수 있어요. 늦게 신청하면 남은 날을 다
        받지 못할 수 있으니 미루지 마세요.
      </p>
      {state.age_at_separation >= 65 && (
        <p className="bg-warn-soft text-warn rounded-xl px-4 py-3 text-base">
          65세 이후에 새로 고용됐거나 자영업을 시작했다면 실업급여가 적용되지 않을 수 있어요.
          고용센터에 확인해 주세요.
        </p>
      )}
      {!isReadOnly && !isApplied && personaId && (
        <ProcedureFactForm
          personaId={personaId}
          path="/eligibility_applied_on"
          dateLabel="수급자격 신청일"
          defaultDate={state.demo_today}
          buttonLabel="신청을 마쳤어요"
          hint="고용센터에서 수급자격 신청을 마쳤으면 신청한 날을 넣어 주세요. 다음 단계에서 1차 실업인정일을 받아요."
        />
      )}
      <EvidenceLine cite={SOURCE} />
    </div>
  );
};

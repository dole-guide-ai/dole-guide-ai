import { EvidenceLine } from '@/components/EvidenceLine';
import { FieldRow } from '@/features/resume/FieldRow';
import { ProcedureFactForm } from '@/features/steps/ProcedureFactForm';

import { formatShortDate } from '@/lib/dateFormat';
import { citeOf } from '@/lib/sources';
import type { UserState } from '@/types/demo.types';

/**
 * E5b 1차 실업인정일 입력 요청 (1.6 · 1.8): 수급자격 신청을 마친 뒤 패널 B 자리에 보입니다.
 * 날짜를 직접 넣거나(`PATCH …/procedure`, F-16), 안내문 파일·날짜를 대화로 알려 줄 수 있습니다.
 */
interface FirstDatePanelProps {
  state: UserState;
  /** 있으면 1차 실업인정일 입력을 보입니다 */
  personaId?: string;
}

const SOURCE = citeOf('SRC-011', 'SRC-013');

export const FirstDatePanel = ({ state, personaId }: FirstDatePanelProps) => (
  <div className="flex flex-col gap-4">
    <div className="border-brand/30 bg-brand-soft/40 flex flex-col gap-2 rounded-2xl border px-5 py-4">
      <p className="text-lg font-bold">1차 실업인정일을 알려 주세요</p>
      <p className="text-base">
        고용센터에서 받은 안내문에 1차 실업인정일이 적혀 있어요. 안내문을 파일(사진·문서)로 올리거나
        날짜를 말씀해 주시면, 그날까지 할 일을 정리해 드릴게요.
      </p>
    </div>
    {personaId && !state.next_recognition_date && (
      <ProcedureFactForm
        personaId={personaId}
        path="/first_recognition_date"
        dateLabel="1차 실업인정일"
        buttonLabel="인정일 저장"
      />
    )}
    <dl className="divide-line divide-y">
      <FieldRow
        label="수급자격 신청일"
        value={
          state.eligibility_applied_date ? formatShortDate(state.eligibility_applied_date) : null
        }
        chip={{ label: '자동', tone: 'neutral' }}
      />
      <FieldRow
        label="1차 실업인정일"
        value={state.next_recognition_date ? formatShortDate(state.next_recognition_date) : null}
      />
    </dl>
    {/* DUE-057: 대기기간은 실업 신고일부터 셉니다 (건설일용 예외는 별도). */}
    <p className="bg-canvas text-ink rounded-xl px-4 py-3 text-base">
      실업 신고일부터 7일은 대기기간이라 구직급여가 나오지 않아요. 1차 실업인정 때 받는 금액이
      생각보다 적을 수 있어요.
    </p>
    <EvidenceLine cite={SOURCE} />
  </div>
);

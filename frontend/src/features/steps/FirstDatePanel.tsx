import { EvidenceLine } from '@/components/EvidenceLine';
import { FieldRow } from '@/features/resume/FieldRow';

import { formatShortDate } from '@/lib/dateFormat';
import type { UserState } from '@/types/demo.types';

/**
 * E5b 1차 실업인정일 입력 요청 (1.6 · 1.8): 수급자격 신청을 마친 뒤 패널 B 자리에 보입니다.
 * 대화 과정은 기획 "예정"이라, 안내문 사진이나 날짜를 대화로 알려 달라는 정적 안내만 둡니다.
 */
interface FirstDatePanelProps {
  state: UserState;
}

const SOURCE = '찾기쉬운 생활법령정보';

export const FirstDatePanel = ({ state }: FirstDatePanelProps) => (
  <div className="flex flex-col gap-4">
    <div className="border-brand/30 bg-brand-soft/40 flex flex-col gap-2 rounded-2xl border px-5 py-4">
      <p className="text-lg font-bold">1차 실업인정일을 알려 주세요</p>
      <p className="text-base">
        고용센터에서 받은 안내문에 1차 실업인정일이 적혀 있어요. 안내문을 사진으로 올리거나 날짜를
        말씀해 주시면, 그날까지 할 일을 정리해 드릴게요.
      </p>
    </div>
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
    <EvidenceLine cite={SOURCE} />
  </div>
);

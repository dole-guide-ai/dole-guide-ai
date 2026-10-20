import type { FormUpdateEvent } from '@/types/chat.types';
import type { MyDataItem } from '@/types/myData.types';

/**
 * 내 정보 모의 스냅샷 (2-0.9). 확정된 값 요약 · 절차 상태 · 이용자가 확인한 사실.
 * 지우면 돌려줄 `form_update`(그 값을 쓰던 칸을 `아직 없음`으로)도 같이 둡니다.
 */
export const MOCK_NOT_STORED = [
  '주민등록번호',
  '이름·연락처·주소·이메일',
  '계좌번호',
  '사업장 이메일·전화번호',
  '서류·음성 원본',
  '건강 관련 이직 사유',
];

export const MOCK_MY_DATA: Record<string, MyDataItem[]> = {
  park: [
    {
      item_id: 'procedure.stage',
      group: 'procedure',
      label: '절차 단계',
      value: '구직등록 (이력서 작성 중)',
      is_deletable: false,
    },
  ],
  choi: [
    {
      item_id: 'resume.saved',
      group: 'resume',
      label: '이력서',
      value: '2019년 예전 이력서 (최신화 중)',
      is_deletable: false,
    },
    {
      item_id: 'procedure.stage',
      group: 'procedure',
      label: '절차 단계',
      value: '구직등록 (이력서 최신화)',
      is_deletable: false,
    },
  ],
  lee: [
    {
      item_id: 'resume.saved',
      group: 'resume',
      label: '이력서',
      value: '저장 완료 (일반 사무)',
      is_deletable: false,
    },
    {
      item_id: 'procedure.stage',
      group: 'procedure',
      label: '절차 단계',
      value: '실업인정 4차 준비',
      is_deletable: false,
    },
    {
      item_id: 'procedure.next_recognition_date',
      group: 'procedure',
      label: '다음 실업인정일',
      value: '12.22(화) · 고용센터 출석',
      is_deletable: false,
    },
    {
      item_id: 'facts.unemployment_credit',
      group: 'facts',
      label: '실업크레딧 답',
      value: '희망함 · 전자고지 · 자동이체 희망하지 않음 · 재산 소득 확인 동의함',
      confirmed_on: '2026-11-24',
      is_deletable: true,
    },
    {
      item_id: 'facts.payment_notification_method',
      group: 'facts',
      label: '지급 결정 통지 방법',
      value: '휴대전화 문자메시지',
      confirmed_on: '2026-11-24',
      is_deletable: true,
    },
  ],
};

const MISSING = { status: 'missing' } as const;

export const MOCK_MY_DATA_DELETE_UPDATES: Record<string, FormUpdateEvent[]> = {
  'facts.unemployment_credit': [
    {
      form: 'recognition',
      path: 'unemployment_credit',
      op: 'set',
      value: {
        is_applicable: true,
        credit_application_choice: null,
        notice_delivery_method: null,
        automatic_payment_choice: null,
        income_asset_consent: null,
        answered_on: null,
      },
      ...MISSING,
    },
  ],
  'facts.payment_notification_method': [
    {
      form: 'recognition',
      path: 'notification_and_plan.payment_notification_method',
      op: 'set',
      value: null,
      ...MISSING,
    },
  ],
};

import type { components } from '@/types/api.gen';

type FactList = components['schemas']['FactList'];

/** 이정호 내 정보 `GET /accounts/lee/facts` 응답 (합성 값). 절차·이력서 줄은 지울 수 없습니다. */
export const LEE_FACTS: FactList = {
  items: [
    {
      fact_id: 'resume.saved',
      group: 'resume',
      label: '이력서',
      value: '저장 완료 (일반 사무)',
      answered_on: null,
      is_deletable: false,
    },
    {
      fact_id: 'procedure.stage',
      group: 'procedure',
      label: '절차 단계',
      value: '실업인정 4차 준비',
      answered_on: null,
      is_deletable: false,
    },
    {
      fact_id: 'credit.application',
      group: 'facts',
      label: '실업크레딧 답',
      value: '희망함',
      answered_on: '2026-11-24',
      is_deletable: true,
    },
    {
      fact_id: 'notification_method',
      group: 'facts',
      label: '지급 결정 통지 방법',
      value: '휴대전화 문자메시지',
      answered_on: '2026-11-24',
      is_deletable: true,
    },
  ],
  total: 4,
  not_stored: ['주민등록번호', '이름·연락처·주소·이메일', '계좌번호'],
};

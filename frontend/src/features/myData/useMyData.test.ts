import { describe, expect, it } from 'vitest';

import { myDataFromFacts } from '@/features/myData/useMyData';

describe('myDataFromFacts', () => {
  it('백엔드 내 정보를 창 모양으로 바꿉니다', () => {
    const data = myDataFromFacts({
      items: [
        {
          fact_id: 'application.credit',
          group: 'facts',
          label: '실업크레딧 답',
          value: '희망함',
          answered_on: '2026-11-24',
          is_deletable: true,
        },
        {
          fact_id: 'procedure.stage',
          group: 'procedure',
          label: '절차 단계',
          value: null,
          is_deletable: false,
        },
      ],
      total: 2,
      not_stored: ['주민등록번호'],
    });
    expect(data.items[0]).toEqual({
      item_id: 'application.credit',
      group: 'facts',
      label: '실업크레딧 답',
      value: '희망함',
      confirmed_on: '2026-11-24',
      is_deletable: true,
    });
    expect(data.items[1].value).toBe('');
    expect(data.not_stored).toEqual(['주민등록번호']);
  });
});

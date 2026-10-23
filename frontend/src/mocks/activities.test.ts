import { describe, expect, it } from 'vitest';

import { MOCK_ROUND_CHECKS, mockRecommendations } from '@/mocks/activities';

describe('mockRecommendations (F-19)', () => {
  it('4차는 인정된 활동이 있는 날을 피해 인정일 전날까지로 권한다', () => {
    const result = mockRecommendations('lee', '2026-12-22', MOCK_ROUND_CHECKS.lee.activities);

    expect(result?.deadline_text).toBe(
      '12월 8일이 아닌 다른 날, 인정일 전날 12월 21일(월)까지 하시길 권해요.',
    );
    expect(result?.items.map((item) => item.recommendation_id)).toEqual([
      'rec_work24_apply',
      'rec_step_online',
      'rec_interview',
    ]);
  });

  it('5차로 넘어가면 5차 인정일 기준으로 다시 정한다 (점검 11, N5)', () => {
    const result = mockRecommendations('lee', '2027-01-19', []);

    expect(result?.deadline_text).toBe('인정일 전날 1월 18일(월)까지 하시길 권해요.');
  });
});

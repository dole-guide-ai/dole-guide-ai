import { useProcedurePatch } from '@/features/procedure/useProcedurePatch';

/**
 * 추천의 `선택` (2-2.8): `PATCH /procedure`로 예정 활동(`planned`)을 더합니다.
 * 예정 활동은 계산에 넣지 않습니다.
 */
export const usePlanActivity = () =>
  useProcedurePatch((recommendationId: string) => ({
    path: 'activities',
    op: 'append',
    value: { recommendation_id: recommendationId },
  }));

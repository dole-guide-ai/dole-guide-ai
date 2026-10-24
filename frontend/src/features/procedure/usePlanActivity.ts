import { useMutation, useQueryClient } from '@tanstack/react-query';

import { apiFetch } from '@/lib/api';
import { API_PATHS } from '@/lib/apiPaths';
import { applyFormUpdates } from '@/lib/formStore';
import { IDEMPOTENCY_HEADER } from '@/lib/idempotency';
import { queryKeys } from '@/lib/queryKeys';
import type { FormPatchRead } from '@/types/chat.types';

/**
 * 추천의 `선택` (F-19, 2-2.8): `POST /accounts/{id}/activities`에 추천 ID만 보내 예정 활동으로 넣습니다.
 * 응답의 다시 계산한 회차 점검(`/round_check`)을 패널 B에 적용하고, 고른 추천이 남지 않게 추천 목록을 새로 받습니다.
 * 두 번 눌려도 한 번만 들어가게 Idempotency-Key를 붙입니다.
 */
export const usePlanActivity = (sessionId: string, personaId: string) => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (recommendationId: string) =>
      apiFetch<FormPatchRead>(API_PATHS.activities(personaId), {
        method: 'POST',
        headers: { [IDEMPOTENCY_HEADER]: `plan-${recommendationId}` },
        body: JSON.stringify({ recommendation_id: recommendationId }),
      }),
    onSuccess: (result) => {
      applyFormUpdates(result);
      void queryClient.invalidateQueries({
        queryKey: queryKeys.roundRecommendationsPrefix(sessionId),
      });
    },
  });
};

import { useMutation, useQueryClient } from '@tanstack/react-query';

import { isServerSession } from '@/lib/accountSession';
import { apiFetch, apiSend } from '@/lib/api';
import { API_PATHS } from '@/lib/apiPaths';
import { applyFormUpdates } from '@/lib/formStore';
import { queryKeys } from '@/lib/queryKeys';
import type { FormPatchRead } from '@/types/chat.types';
import type { ProcedurePatchCreate } from '@/types/procedure.types';

/**
 * 추천의 `선택` (2-2.8): `PATCH /procedure`로 예정 활동(`planned`)을 더하고,
 * 서버가 돌려준 `form_update`들을 그대로 저장소에 적용합니다. 예정 활동은 계산에 넣지 않습니다.
 * 실제 서버 세션(`acct-`)이면 `POST /accounts/{id}/activities`에 추천 ID만 보내고(F-19),
 * 회차 점검을 다시 받습니다. 두 번 눌려도 한 번만 들어가게 Idempotency-Key를 붙입니다.
 */
export const usePlanActivity = (sessionId?: string, personaId?: string) => {
  const queryClient = useQueryClient();
  const isServer = sessionId !== undefined && isServerSession(sessionId) && !!personaId;

  return useMutation({
    mutationFn: (recommendationId: string) => {
      if (isServer) {
        return apiFetch<FormPatchRead>(API_PATHS.activities(personaId), {
          method: 'POST',
          headers: { 'Idempotency-Key': `plan-${recommendationId}` },
          body: JSON.stringify({ recommendation_id: recommendationId }),
        });
      }
      const body: ProcedurePatchCreate = {
        path: 'activities',
        op: 'append',
        value: { recommendation_id: recommendationId },
      };
      return apiSend<FormPatchRead>(API_PATHS.LEGACY_PROCEDURE, 'PATCH', body);
    },
    onSuccess: (result) => {
      if (isServer) {
        void queryClient.invalidateQueries({ queryKey: queryKeys.roundCheckPrefix(sessionId) });
        // 고른 추천이 다시 열었을 때도 선택 가능하게 남지 않도록 추천 목록도 새로 받습니다.
        void queryClient.invalidateQueries({
          queryKey: queryKeys.roundRecommendationsPrefix(sessionId),
        });
        return;
      }
      applyFormUpdates(result);
    },
  });
};

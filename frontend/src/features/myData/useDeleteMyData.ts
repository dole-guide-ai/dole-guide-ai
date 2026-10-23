import { useMutation, useQueryClient } from '@tanstack/react-query';

import { isServerSession } from '@/lib/accountSession';
import { apiFetch, apiSend } from '@/lib/api';
import { API_PATHS } from '@/lib/apiPaths';
import { applyFormUpdates } from '@/lib/formStore';
import { queryKeys } from '@/lib/queryKeys';
import type { MyDataDelete, MyDataDeleteRead } from '@/types/myData.types';

const DELETE = 'DELETE';

/**
 * 내 정보 한 줄 삭제 (2-0.9). AI는 필요할 때 다시 묻습니다.
 * - 모의 세션: `DELETE /me/data` → 돌려준 `form_update`로 그 칸을 `아직 없음`으로
 * - 실제 서버 세션: `DELETE /accounts/{id}/facts/{fact_id}`(F-31) 뒤 이력서·신청서를 다시 받아
 *   그 칸이 `답변 필요`로 보이게 합니다.
 */
export const useDeleteMyData = (sessionId: string, personaId?: string) => {
  const queryClient = useQueryClient();
  const isServer = isServerSession(sessionId) && !!personaId;

  return useMutation({
    mutationFn: async (body: MyDataDelete) => {
      if (!isServer) return apiSend<MyDataDeleteRead>(API_PATHS.LEGACY_MY_DATA, DELETE, body);
      await apiFetch(API_PATHS.facts(personaId, body.item_id), { method: DELETE });
      return null;
    },
    onSuccess: (result) => {
      if (result) applyFormUpdates(result);
      else void queryClient.invalidateQueries({ queryKey: queryKeys.forms });
      void queryClient.invalidateQueries({ queryKey: queryKeys.myData(sessionId) });
    },
  });
};

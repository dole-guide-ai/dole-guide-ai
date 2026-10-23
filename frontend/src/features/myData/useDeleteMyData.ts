import { useMutation, useQueryClient } from '@tanstack/react-query';

import { apiFetch } from '@/lib/api';
import { API_PATHS } from '@/lib/apiPaths';
import { applyFormUpdates } from '@/lib/formStore';
import { queryKeys } from '@/lib/queryKeys';
import type { FormPatchRead } from '@/types/chat.types';

const DELETE = 'DELETE';

/**
 * 내 정보 한 줄 삭제 `DELETE /accounts/{id}/facts/{fact_id}` (F-31, 2-0.9). AI는 필요할 때 다시 묻습니다.
 * 지운 뒤 이력서·신청서를 다시 받아 그 칸이 `답변 필요`로 보이게 합니다.
 */
export const useDeleteMyData = (sessionId: string, personaId: string) => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (factId: string) =>
      apiFetch<FormPatchRead>(API_PATHS.facts(personaId, factId), { method: DELETE }),
    onSuccess: (result) => {
      // 지운 칸(답변 필요로 돌아간 칸)을 바로 반영하고, 서류도 다시 받습니다.
      applyFormUpdates(result);
      void queryClient.invalidateQueries({ queryKey: queryKeys.forms });
      void queryClient.invalidateQueries({ queryKey: queryKeys.myData(sessionId) });
    },
  });
};

import { useMutation } from '@tanstack/react-query';

import { apiFetch } from '@/lib/api';
import { API_PATHS } from '@/lib/apiPaths';
import { applyFormUpdates } from '@/lib/formStore';
import type { FormPatchRead } from '@/types/chat.types';

/**
 * 활동 빼기 (F-20, 2-2.11): `DELETE /accounts/{id}/activities/{activity_id}`.
 * 서버가 다시 계산한 회차 점검(`/round_check`)을 돌려주면 패널 B에 그대로 적용합니다.
 */
export const useRemoveActivity = (personaId: string) =>
  useMutation({
    mutationFn: (activityId: string) =>
      apiFetch<FormPatchRead>(API_PATHS.activity(personaId, activityId), { method: 'DELETE' }),
    onSuccess: applyFormUpdates,
  });

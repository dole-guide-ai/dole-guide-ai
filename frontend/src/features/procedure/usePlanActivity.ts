import { useMutation } from '@tanstack/react-query';

import { apiFetch } from '@/lib/api';
import { applyFormUpdate } from '@/lib/formStore';
import type { FormPatchRead } from '@/types/chat.types';
import type { ProcedurePatchCreate } from '@/types/procedure.types';

/**
 * 추천의 `선택` (2-2.8): `PATCH /procedure`로 예정 활동(`planned`)을 더하고,
 * 서버가 돌려준 `form_update`들을 그대로 저장소에 적용합니다. 예정 활동은 계산에 넣지 않습니다.
 */
export const usePlanActivity = () =>
  useMutation({
    mutationFn: (recommendationId: string) => {
      const body: ProcedurePatchCreate = {
        path: 'activities',
        op: 'append',
        value: { recommendation_id: recommendationId },
      };
      return apiFetch<FormPatchRead>('/procedure', { method: 'PATCH', body: JSON.stringify(body) });
    },
    onSuccess: ({ updates }) => updates.forEach(applyFormUpdate),
  });

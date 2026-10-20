import { useMutation } from '@tanstack/react-query';

import { apiFetch } from '@/lib/api';
import { applyFormUpdate } from '@/lib/formStore';
import type { FormPatchRead } from '@/types/chat.types';
import type { ProcedurePatchCreate } from '@/types/procedure.types';

/**
 * 활동 빼기 (2-2.11): `PATCH /procedure { path: "activities.{item_id}", op: "remove" }`.
 * 서버가 회차 점검을 다시 계산해 돌려준 `form_update`들(목록·인정 건수·경고)을 그대로 적용합니다.
 */
export const useRemoveActivity = () =>
  useMutation({
    mutationFn: (itemId: string) => {
      const body: ProcedurePatchCreate = { path: `activities.${itemId}`, op: 'remove' };
      return apiFetch<FormPatchRead>('/procedure', { method: 'PATCH', body: JSON.stringify(body) });
    },
    onSuccess: ({ updates }) => updates.forEach(applyFormUpdate),
  });

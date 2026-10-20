import { useMutation, useQueryClient } from '@tanstack/react-query';

import { apiFetch } from '@/lib/api';
import { applyFormUpdate } from '@/lib/formStore';
import { queryKeys } from '@/lib/queryKeys';
import type { MyDataDelete, MyDataDeleteRead } from '@/types/myData.types';

/**
 * 내 정보 한 줄 삭제 (2-0.9): `DELETE /me/data`. 서버가 돌려준 `form_update`로 그 값을 쓰던 패널 칸을
 * `아직 없음`으로 돌리고, 목록을 다시 받습니다. AI는 필요할 때 다시 묻습니다.
 */
export const useDeleteMyData = (sessionId: string) => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (body: MyDataDelete) =>
      apiFetch<MyDataDeleteRead>('/me/data', { method: 'DELETE', body: JSON.stringify(body) }),
    onSuccess: ({ updates }) => {
      updates.forEach(applyFormUpdate);
      void queryClient.invalidateQueries({ queryKey: queryKeys.myData(sessionId) });
    },
  });
};

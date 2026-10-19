import { useMutation, useQueryClient } from '@tanstack/react-query';

import { apiFetch } from '@/lib/api';
import { queryKeys } from '@/lib/queryKeys';
import { setSession } from '@/lib/sessionStore';
import type { SessionRead } from '@/types/demo.types';

/**
 * `POST /forms/resume/confirm` (2-1.6 저장). 이력서가 `finalized`가 되고 단계가 온라인 교육으로 넘어가므로,
 * 응답으로 새 세션(상태·파생값·진입 결과)을 받아 그대로 바꿔 끼웁니다.
 */
export const useConfirmResume = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: () =>
      apiFetch<SessionRead>('/forms/resume/confirm', { method: 'POST', body: '{}' }),
    onSuccess: (session) => {
      setSession(session);
      void queryClient.invalidateQueries({ queryKey: queryKeys.forms });
    },
  });
};

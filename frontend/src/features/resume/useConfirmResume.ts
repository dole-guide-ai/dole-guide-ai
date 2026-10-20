import { useMutation, useQueryClient } from '@tanstack/react-query';

import { apiFetch } from '@/lib/api';
import { applyFormUpdate } from '@/lib/formStore';
import { queryKeys } from '@/lib/queryKeys';
import { getSession, setSession } from '@/lib/sessionStore';
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
      // 이미 저장한 이력서를 고쳐 다시 저장하면(2-1.6) 단계가 그대로라 지금 초안을 확정 상태로만 바꿉니다.
      if (getSession()?.state.resume_status === 'ready') {
        applyFormUpdate({ form: 'resume', path: 'status', op: 'set', value: 'finalized' });
        applyFormUpdate({ form: 'resume', path: 'can_save', op: 'set', value: false });
        return;
      }
      setSession(session);
      void queryClient.invalidateQueries({ queryKey: queryKeys.forms });
    },
  });
};

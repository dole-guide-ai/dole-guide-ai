import { useMutation } from '@tanstack/react-query';

import { sessionFromAccount } from '@/lib/accountSession';
import { apiFetch } from '@/lib/api';
import { API_PATHS } from '@/lib/apiPaths';
import { resetForms } from '@/lib/formStore';
import { setSession } from '@/lib/sessionStore';
import type { components } from '@/types/api.gen';

type AccountRead = components['schemas']['AccountRead'];

/**
 * 개발용 처음부터 다시: `DELETE /accounts/{id}`(서류·회차·활동·대화 삭제) → `PUT`으로 seed 상태로 다시 입장.
 * 대화·양식 캐시가 남지 않게 화면을 새로 불러옵니다.
 */
export const useResetAccount = (personaId: string) =>
  useMutation({
    mutationFn: async () => {
      await apiFetch<void>(API_PATHS.account(personaId), { method: 'DELETE' });
      const account = await apiFetch<AccountRead>(API_PATHS.account(personaId), {
        method: 'PUT',
      });
      return sessionFromAccount(account);
    },
    onSuccess: (session) => {
      resetForms();
      setSession(session);
      window.location.reload();
    },
  });

import { useRouter } from 'next/navigation';

import { useMutation } from '@tanstack/react-query';

import { sessionFromAccount } from '@/lib/accountSession';
import { apiFetch } from '@/lib/api';
import { API_PATHS } from '@/lib/apiPaths';
import { resetForms } from '@/lib/formStore';
import { setSession } from '@/lib/sessionStore';
import type { components } from '@/types/api.gen';

type AccountRead = components['schemas']['AccountRead'];

const RETRY_TEXT =
  '초기화 중 문제가 생겨 계정을 다시 만들지 못했어요. 첫 화면에서 계정을 다시 골라 주세요.';

/**
 * "처음부터 다시": `DELETE /accounts/{id}`(서류·회차·활동·대화 삭제) → `PUT`으로 seed 상태로 다시 입장.
 * 대화·양식 캐시가 남지 않게 화면을 새로 불러옵니다.
 * DELETE 뒤 PUT이 실패하면 계정은 이미 지워진 상태라, 지난 세션을 비우고 첫 화면으로 보냅니다
 * (거기서 계정을 고르면 PUT이 다시 실행돼 seed 상태로 만들어집니다).
 */
export const useResetAccount = (personaId: string) => {
  const router = useRouter();

  return useMutation({
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
    onError: () => {
      resetForms();
      setSession(null);
      window.alert(RETRY_TEXT);
      router.push('/');
    },
  });
};

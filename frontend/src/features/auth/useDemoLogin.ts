import { useRouter } from 'next/navigation';

import { useMutation } from '@tanstack/react-query';

import { sessionFromAccount } from '@/lib/accountSession';
import { apiFetch } from '@/lib/api';
import { API_PATHS } from '@/lib/apiPaths';
import { setSession } from '@/lib/sessionStore';
import type { components } from '@/types/api.gen';

type AccountRead = components['schemas']['AccountRead'];

/**
 * 카드 클릭 → `PUT /accounts/{id}`(처음이면 seed로 만들고, 있으면 이어서) → 대시보드 (F-01, 설계 3.2).
 * 방문자 쿠키는 BFF가 알아서 만듭니다.
 */
export const useDemoLogin = () => {
  const router = useRouter();

  return useMutation({
    mutationFn: async (personaId: string) => {
      const account = await apiFetch<AccountRead>(API_PATHS.account(personaId), {
        method: 'PUT',
      });
      return sessionFromAccount(account);
    },
    onSuccess: (session) => {
      setSession(session);
      router.push('/dashboard');
    },
  });
};

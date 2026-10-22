import { useRouter } from 'next/navigation';

import { useMutation } from '@tanstack/react-query';

import { sessionFromAccount } from '@/lib/accountSession';
import { apiFetch } from '@/lib/api';
import { API_PATHS } from '@/lib/apiPaths';
import { usesMockScreens } from '@/lib/mockMode';
import { setSession } from '@/lib/sessionStore';
import type { components } from '@/types/api.gen';
import { buildMockSession, enterMockAccount } from '@/mocks/handlers';

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
      // 혼합 모드: 계정은 실제 백엔드에 만들고, 로그인 이후 화면은 아직 mock 대본을 쓰므로
      // 화면 세션도 이전과 같은 mock 세션을 씁니다. 화면을 백엔드로 옮기면 이 분기를 지웁니다.
      if (usesMockScreens()) {
        enterMockAccount(account.persona_id);
        return buildMockSession(account.persona_id);
      }
      return sessionFromAccount(account);
    },
    onSuccess: (session) => {
      setSession(session);
      router.push('/dashboard');
    },
  });
};

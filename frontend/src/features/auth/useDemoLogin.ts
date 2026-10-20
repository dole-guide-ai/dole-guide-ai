import { useRouter } from 'next/navigation';

import { useMutation } from '@tanstack/react-query';

import { apiFetch } from '@/lib/api';
import { setSession } from '@/lib/sessionStore';
import type { DemoAuthCreate, DemoAuthRead, SessionRead } from '@/types/demo.types';

/**
 * 카드 클릭 → `POST /auth/demo`(seed로 초기화) → `POST /sessions`(진입 결과) → 대시보드 (1.4, 1.11).
 * `계정 바꾸기` 뒤 다시 고를 때도 같은 흐름이라 seed 상태로 돌아갑니다.
 */
export const useDemoLogin = () => {
  const router = useRouter();

  return useMutation({
    mutationFn: async (personaId: string) => {
      const body: DemoAuthCreate = { persona_id: personaId };
      await apiFetch<DemoAuthRead>('/auth/demo', { method: 'POST', body: JSON.stringify(body) });
      return apiFetch<SessionRead>('/sessions', { method: 'POST', body: JSON.stringify({}) });
    },
    onSuccess: (session) => {
      setSession(session);
      router.push('/dashboard');
    },
  });
};

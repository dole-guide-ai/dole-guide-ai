import { useRouter } from 'next/navigation';

import { useMutation } from '@tanstack/react-query';

import { sessionFromAccount } from '@/lib/accountSession';
import { ApiError, apiFetch } from '@/lib/api';
import { API_PATHS } from '@/lib/apiPaths';
import { resetForms } from '@/lib/formStore';
import { setSession } from '@/lib/sessionStore';
import type { components } from '@/types/api.gen';

type AccountRead = components['schemas']['AccountRead'];

const RETRY_TEXT =
  '초기화 중 문제가 생겨 계정을 다시 만들지 못했어요. 첫 화면에서 계정을 다시 골라 주세요.';
const DELETE_FAILED_TEXT = '초기화하지 못했어요. 잠시 후 다시 눌러 주세요.';
const HTTP_CONFLICT = 409;

/** 어느 단계에서 실패했는지 구분합니다. DELETE 실패면 계정이 그대로라 화면을 지키고, PUT 실패면 첫 화면으로 보냅니다. */
const RESET_STEP = { DELETE: 'delete', RECREATE: 'recreate' } as const;
type ResetStep = (typeof RESET_STEP)[keyof typeof RESET_STEP];

class ResetAccountError extends Error {
  constructor(
    readonly step: ResetStep,
    readonly cause?: unknown,
  ) {
    super(`reset failed at ${step}`);
  }
}

/**
 * "처음부터 다시": `DELETE /accounts/{id}`(서류·회차·활동·대화 삭제) → `PUT`으로 seed 상태로 다시 입장.
 * 대화·양식 캐시가 남지 않게 화면을 새로 불러옵니다.
 * - DELETE가 실패하면 계정은 그대로라 세션·양식을 지키고, 다시 눌러 달라고 안내합니다.
 * - DELETE 뒤 PUT이 실패하면 계정은 이미 지워진 상태라, 지난 세션을 비우고 첫 화면으로 보냅니다
 *   (거기서 계정을 고르면 PUT이 다시 실행돼 seed 상태로 만들어집니다).
 */
export const useResetAccount = (personaId: string) => {
  const router = useRouter();

  return useMutation({
    mutationFn: async () => {
      await apiFetch<void>(API_PATHS.account(personaId), { method: 'DELETE' }).catch((error) => {
        throw new ResetAccountError(RESET_STEP.DELETE, error);
      });
      const account = await apiFetch<AccountRead>(API_PATHS.account(personaId), {
        method: 'PUT',
      }).catch(() => {
        throw new ResetAccountError(RESET_STEP.RECREATE);
      });
      return sessionFromAccount(account);
    },
    onSuccess: (session) => {
      resetForms();
      setSession(session);
      window.location.reload();
    },
    onError: (error) => {
      if (error instanceof ResetAccountError && error.step === RESET_STEP.DELETE) {
        // 답을 만드는 중(409 TURN_IN_PROGRESS)이면 서버 문구를 그대로, 그 밖은 다시 눌러 달라고 안내합니다.
        const busy = error.cause instanceof ApiError && error.cause.status === HTTP_CONFLICT;
        window.alert(busy ? error.cause.message : DELETE_FAILED_TEXT);
        return;
      }
      resetForms();
      setSession(null);
      window.alert(RETRY_TEXT);
      router.push('/');
    },
  });
};

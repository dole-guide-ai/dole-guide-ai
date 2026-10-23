import { useMutation } from '@tanstack/react-query';

import { applyFormUpdateEvent } from '@/features/chat/applyFormUpdateEvent';

import { sessionFromAccount } from '@/lib/accountSession';
import { apiFetch, usesMock } from '@/lib/api';
import { setSession } from '@/lib/sessionStore';
import type { components } from '@/types/api.gen';
import type { FormUpdateEvent } from '@/types/chat.types';

type AccountRead = components['schemas']['AccountRead'];
type UpdatesRead = components['schemas']['UpdatesRead'];

/** 고용센터에서 받은 사실 하나 (설계 3.4): 교육 이수 · 수급자격 신청일 · 1차 실업인정일 */
export type ProcedureFact =
  | { path: '/education_done'; value: true }
  | { path: '/eligibility_applied_on'; value: string }
  | { path: '/first_recognition_date'; value: string };

const reloadAccount = async (personaId: string) => {
  const account = await apiFetch<AccountRead>(`/accounts/${encodeURIComponent(personaId)}`);
  setSession(sessionFromAccount(account));
};

/**
 * `PATCH /accounts/{id}/procedure` (F-16). 단계가 바뀌므로 성공하면 화면 세션을 새로 맞춥니다.
 * - 실제 서버 화면: 계정을 다시 불러와(`GET /accounts/{id}`) 세션을 통째로 바꿉니다.
 *   저장은 됐는데 다시 불러오기만 실패하면 `{ reloaded: false }`로 끝내, 같은 사실을 다시 보내지 않게 합니다.
 * - 모의 화면: 모의 응답의 `form_update`(form: procedure)를 대화와 같은 방식으로 반영합니다.
 */
export const useProcedurePatch = (personaId: string) =>
  useMutation({
    mutationFn: async (fact: ProcedureFact): Promise<{ reloaded: boolean }> => {
      const path = `/accounts/${encodeURIComponent(personaId)}/procedure`;
      const result = await apiFetch<UpdatesRead>(path, {
        method: 'PATCH',
        body: JSON.stringify([{ op: 'replace', ...fact }]),
      });
      if (usesMock('/screens')) {
        (result.updates as FormUpdateEvent[]).forEach(applyFormUpdateEvent);
        return { reloaded: true };
      }
      try {
        await reloadAccount(personaId);
        return { reloaded: true };
      } catch {
        return { reloaded: false };
      }
    },
  });

/** 저장 뒤 계정 다시 불러오기만 실패했을 때 그것만 다시 합니다. */
export const useAccountReload = (personaId: string) =>
  useMutation({ mutationFn: () => reloadAccount(personaId) });

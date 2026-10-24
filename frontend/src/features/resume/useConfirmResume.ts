import { useMutation, useQueryClient } from '@tanstack/react-query';

import { resumeIfMatch } from '@/features/resume/usePatchResumeField';
import { resumePath } from '@/features/resume/useResumeForm';

import { sessionFromAccount } from '@/lib/accountSession';
import { apiFetch } from '@/lib/api';
import { IF_MATCH_HEADER } from '@/lib/etag';
import { queryKeys } from '@/lib/queryKeys';
import { setSession } from '@/lib/sessionStore';
import type { components } from '@/types/api.gen';
import type { SessionRead } from '@/types/demo.types';

type AccountRead = components['schemas']['AccountRead'];
type UpdatesRead = components['schemas']['UpdatesRead'];

/**
 * 실제 서버: `PATCH /accounts/{id}/resume`로 `/status`를 saved로 바꾸고(F-15), 계정을 다시 받아 세션을 바꿉니다.
 * 첫 화면은 저장 응답의 entry(저장 안내·고용24 입력 안내 포함)를 씁니다.
 */
const saveToServer = async (personaId: string): Promise<SessionRead> => {
  const saved = await apiFetch<UpdatesRead>(resumePath(personaId), {
    method: 'PATCH',
    headers: { [IF_MATCH_HEADER]: resumeIfMatch() },
    body: JSON.stringify([{ op: 'replace', path: '/status', value: 'saved' }]),
  });
  const account = await apiFetch<AccountRead>(`/accounts/${encodeURIComponent(personaId)}`);
  const entry = (saved.entry as AccountRead['entry'] | null) ?? account.entry;
  return sessionFromAccount({ ...account, entry });
};

/**
 * 이력서 저장 (2-1.6, F-15). 단계가 온라인 교육으로 넘어가므로(다시 저장이면 단계 그대로)
 * 새 세션(상태·파생값·진입 결과)으로 바꿔 끼웁니다.
 */
export const useConfirmResume = (personaId: string) => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: () => saveToServer(personaId),
    onSuccess: (session) => {
      setSession(session);
      void queryClient.invalidateQueries({ queryKey: queryKeys.forms });
    },
  });
};

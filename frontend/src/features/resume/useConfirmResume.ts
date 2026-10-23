import { useMutation, useQueryClient } from '@tanstack/react-query';

import { resumeIfMatch } from '@/features/resume/usePatchResumeField';
import { resumePath } from '@/features/resume/useResumeForm';

import { isServerSession, sessionFromAccount } from '@/lib/accountSession';
import { apiFetch } from '@/lib/api';
import { applyFormUpdate } from '@/lib/formStore';
import { queryKeys } from '@/lib/queryKeys';
import { getSession, setSession } from '@/lib/sessionStore';
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
    headers: { 'If-Match': resumeIfMatch() },
    body: JSON.stringify([{ op: 'replace', path: '/status', value: 'saved' }]),
  });
  const account = await apiFetch<AccountRead>(`/accounts/${encodeURIComponent(personaId)}`);
  const entry = (saved.entry as AccountRead['entry'] | null) ?? account.entry;
  return sessionFromAccount({ ...account, entry });
};

/**
 * 이력서 저장 (2-1.6). 이력서가 `finalized`가 되고 단계가 온라인 교육으로 넘어가므로,
 * 응답으로 새 세션(상태·파생값·진입 결과)을 받아 그대로 바꿔 끼웁니다.
 * - 모의 세션: `POST /forms/resume/confirm`
 * - 실제 서버 세션: `saveToServer`
 */
export const useConfirmResume = (sessionId?: string, personaId?: string) => {
  const queryClient = useQueryClient();
  const isServer = !!sessionId && isServerSession(sessionId) && !!personaId;

  return useMutation({
    mutationFn: () =>
      isServer
        ? saveToServer(personaId)
        : apiFetch<SessionRead>('/forms/resume/confirm', { method: 'POST', body: '{}' }),
    onSuccess: (session) => {
      // 이미 저장한 이력서를 고쳐 다시 저장하면(2-1.6) 단계가 그대로라 지금 초안을 확정 상태로만 바꿉니다.
      if (!isServer && getSession()?.state.resume_status === 'ready') {
        applyFormUpdate({ form: 'resume', path: 'status', op: 'set', value: 'finalized' });
        applyFormUpdate({ form: 'resume', path: 'can_save', op: 'set', value: false });
        return;
      }
      setSession(session);
      void queryClient.invalidateQueries({ queryKey: queryKeys.forms });
    },
  });
};

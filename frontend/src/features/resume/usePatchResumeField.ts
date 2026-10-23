import { useMutation, useQueryClient } from '@tanstack/react-query';

import { resumePath } from '@/features/resume/useResumeForm';

import { isServerSession } from '@/lib/accountSession';
import { ApiError, apiFetch } from '@/lib/api';
import { API_PATHS } from '@/lib/apiPaths';
import { applyFormUpdate, getFormDrafts } from '@/lib/formStore';
import { queryKeys } from '@/lib/queryKeys';
import { resumePatchOp } from '@/lib/resumeForm';
import type { FormPatchCreate, FormPatchRead } from '@/types/chat.types';

/** 받아 둔 이력서 버전. PATCH의 If-Match로 보내 다른 탭이 먼저 고쳤으면 409로 막습니다. */
export const resumeIfMatch = () => `"${Number(getFormDrafts().resume.values.lock_version ?? 0)}"`;

/**
 * 패널에서 직접 고치기 (2-0.6). 형식이 안 맞으면 422 `ApiError`가 옵니다.
 * - 모의 세션: `PATCH /forms/resume` → 돌려준 `form_update`들을 저장소에 적용
 * - 실제 서버 세션: `PATCH /accounts/{id}/resume`(JSON Patch) 뒤 이력서를 다시 받습니다 (F-15).
 */
export const usePatchResumeField = (sessionId?: string, personaId?: string) => {
  const queryClient = useQueryClient();
  const isServer = !!sessionId && isServerSession(sessionId) && !!personaId;

  return useMutation({
    mutationFn: async (body: FormPatchCreate) => {
      if (!isServer) {
        return apiFetch<FormPatchRead>(API_PATHS.LEGACY_RESUME, {
          method: 'PATCH',
          body: JSON.stringify(body),
        });
      }
      const op = resumePatchOp(body.path, body.value);
      if (!op) throw new ApiError('VALIDATION_ERROR', '이 칸은 대화로 고쳐 주세요.', 422);
      await apiFetch(resumePath(personaId), {
        method: 'PATCH',
        headers: { 'If-Match': resumeIfMatch() },
        body: JSON.stringify([op]),
      });
      return null;
    },
    onSuccess: (read) => {
      if (read) read.updates.forEach(applyFormUpdate);
      else void queryClient.invalidateQueries({ queryKey: queryKeys.resumeForm(sessionId!) });
    },
  });
};

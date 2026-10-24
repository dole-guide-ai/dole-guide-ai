import { useMutation, useQueryClient } from '@tanstack/react-query';

import { resumePath } from '@/features/resume/useResumeForm';

import { ApiError, apiFetch } from '@/lib/api';
import { IF_MATCH_HEADER, ifMatch } from '@/lib/etag';
import { getFormDrafts } from '@/lib/formStore';
import { queryKeys } from '@/lib/queryKeys';
import { resumePatchOp } from '@/lib/resumeForm';
import type { FormPatchCreate } from '@/types/chat.types';

/** 받아 둔 이력서 버전. PATCH의 If-Match로 보내 다른 탭이 먼저 고쳤으면 409로 막습니다. */
export const resumeIfMatch = () =>
  ifMatch(getFormDrafts().resume.values.lock_version as number | undefined);

/**
 * 패널에서 직접 고치기 (2-0.6, F-12). `PATCH /accounts/{id}/resume`(JSON Patch) 뒤 이력서를 다시 받습니다.
 * 형식이 안 맞으면 422 `ApiError`가 옵니다. 여러 칸(기간의 시작·끝)은 한 PATCH로 보내 버전이 한 번만 바뀝니다.
 */
export const usePatchResumeField = (sessionId: string, personaId: string) => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (body: FormPatchCreate | FormPatchCreate[]) => {
      const ops = (Array.isArray(body) ? body : [body]).map((b) => resumePatchOp(b.path, b.value));
      if (ops.some((op) => !op)) {
        throw new ApiError('VALIDATION_ERROR', '이 칸은 대화로 고쳐 주세요.', 422);
      }
      await apiFetch(resumePath(personaId), {
        method: 'PATCH',
        headers: { [IF_MATCH_HEADER]: resumeIfMatch() },
        body: JSON.stringify(ops),
      });
    },
    onSuccess: () =>
      void queryClient.invalidateQueries({ queryKey: queryKeys.resumeForm(sessionId) }),
  });
};

import { useMutation } from '@tanstack/react-query';

import { apiFetch } from '@/lib/api';
import { applyFormUpdate } from '@/lib/formStore';
import type { FormPatchCreate, FormPatchRead } from '@/types/chat.types';

/**
 * 패널에서 직접 고치기 (2-0.6): `PATCH /forms/resume` → 서버가 값 정리(날짜 형식·개수 제한)를 거친 뒤
 * `form_update`들을 돌려주면 그대로 저장소에 적용합니다. 형식이 안 맞으면 422 `ApiError`가 옵니다.
 */
export const usePatchResumeField = () =>
  useMutation({
    mutationFn: (body: FormPatchCreate) =>
      apiFetch<FormPatchRead>('/forms/resume', { method: 'PATCH', body: JSON.stringify(body) }),
    onSuccess: ({ updates }) => updates.forEach(applyFormUpdate),
  });

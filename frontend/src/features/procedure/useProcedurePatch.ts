import { useMutation } from '@tanstack/react-query';

import { apiSend } from '@/lib/api';
import { API_PATHS } from '@/lib/apiPaths';
import { applyFormUpdates } from '@/lib/formStore';
import type { FormPatchRead } from '@/types/chat.types';
import type { ProcedurePatchCreate } from '@/types/procedure.types';

/**
 * 회차 활동을 바꾸는 `PATCH /procedure` 공용 훅. 입력값으로 본문을 만들어 보내고,
 * 서버가 다시 계산해 돌려준 `form_update`들(목록·인정 건수·경고)을 그대로 적용합니다.
 */
export const useProcedurePatch = <TInput>(buildBody: (input: TInput) => ProcedurePatchCreate) =>
  useMutation({
    mutationFn: (input: TInput) =>
      apiSend<FormPatchRead>(API_PATHS.LEGACY_PROCEDURE, 'PATCH', buildBody(input)),
    onSuccess: applyFormUpdates,
  });

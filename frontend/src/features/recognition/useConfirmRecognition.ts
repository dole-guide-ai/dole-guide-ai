import { useMutation, useQueryClient } from '@tanstack/react-query';

import { toRecognitionDraft } from '@/features/recognition/useRecognitionForm';

import { isServerSession } from '@/lib/accountSession';
import { apiFetch } from '@/lib/api';
import { API_PATHS } from '@/lib/apiPaths';
import { recognitionFromApplication } from '@/lib/applicationForm';
import { replaceFormDraft } from '@/lib/formStore';
import { queryKeys } from '@/lib/queryKeys';
import type { components } from '@/types/api.gen';
import type {
  AttendItem,
  RecognitionConfirmCreate,
  RecognitionFormRead,
} from '@/types/recognition.types';

type ApplicationRead = components['schemas']['ApplicationRead'];

interface ConfirmBody extends RecognitionConfirmCreate {
  /** 출석 회차에서 체크한 준비물 (신분증·수급자격증) */
  attend_items?: AttendItem[];
}

/**
 * 실제 서버: `PATCH …/rounds/{round}/application`으로 제출(status → submitted)하고 신청서를 다시 받습니다 (F-27).
 * PATCH가 성공하면 제출은 된 것이라, 다시 받기가 실패해도 성공으로 보고 null을 돌려줍니다.
 */
const submitToServer = async (personaId: string, round: number | null, body: ConfirmBody) => {
  const path = API_PATHS.application(personaId, round);
  const patch = [
    { op: 'replace', path: '/status', value: 'submitted' },
    { op: 'replace', path: '/submit_mode', value: body.submit_mode },
    ...(body.attend_items
      ? [{ op: 'replace', path: '/attend_items', value: body.attend_items }]
      : []),
  ];
  await apiFetch(path, { method: 'PATCH', body: JSON.stringify(patch) });
  try {
    return recognitionFromApplication(await apiFetch<ApplicationRead>(path));
  } catch {
    return null;
  }
};

/**
 * 모의 제출·출석 준비 확인 (2-3.7). 실제 고용24 제출은 하지 않습니다.
 * - 모의 세션: `POST /forms/recognition/confirm { submit_mode }`
 * - 실제 서버 세션: 회차 신청서 PATCH로 제출하고, 다시 받은 신청서로 저장소를 바꿉니다.
 */
export const useConfirmRecognition = (
  sessionId?: string,
  personaId?: string,
  round: number | null = null,
) => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: ConfirmBody): Promise<RecognitionFormRead | null> =>
      sessionId && personaId && isServerSession(sessionId)
        ? submitToServer(personaId, round, body)
        : apiFetch<RecognitionFormRead>(API_PATHS.LEGACY_RECOGNITION_CONFIRM, {
            method: 'POST',
            body: JSON.stringify({ submit_mode: body.submit_mode }),
          }),
    onSuccess: (form, body) => {
      // 신청서 쿼리는 다시 받지 않으므로(staleTime: Infinity) 제출 뒤 값으로 캐시도 바꿉니다.
      const key = sessionId ? queryKeys.recognitionForm(sessionId, round) : null;
      const cached = key ? queryClient.getQueryData<RecognitionFormRead>(key) : undefined;
      // 다시 받기에 실패해도 제출은 끝났으니, 받아 둔 신청서를 제출 완료로 바꿔 버튼을 다시 열지 않습니다.
      const next =
        form ??
        (cached && {
          ...cached,
          status: 'finalized' as const,
          can_submit: false,
          mock_submission:
            body.submit_mode === 'attend' ? ('attend_ready' as const) : ('sent' as const),
        });
      if (next) {
        replaceFormDraft('recognition', toRecognitionDraft(next));
        if (key) queryClient.setQueryData(key, next);
      }
      if (!form && key) void queryClient.invalidateQueries({ queryKey: key });
    },
  });
};

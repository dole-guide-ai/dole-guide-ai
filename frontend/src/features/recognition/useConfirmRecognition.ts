import { useMutation } from '@tanstack/react-query';

import { toRecognitionDraft } from '@/features/recognition/useRecognitionForm';

import { apiFetch } from '@/lib/api';
import { replaceFormDraft } from '@/lib/formStore';
import type { RecognitionConfirmCreate, RecognitionFormRead } from '@/types/recognition.types';

/**
 * 모의 제출·출석 준비 확인 (2-3.7): `POST /forms/recognition/confirm { submit_mode }`.
 * 응답으로 확정된 신청서(`mock_submission`)를 받아 저장소를 바꿉니다. 실제 고용24 제출은 하지 않습니다.
 */
export const useConfirmRecognition = () =>
  useMutation({
    mutationFn: (body: RecognitionConfirmCreate) =>
      apiFetch<RecognitionFormRead>('/forms/recognition/confirm', {
        method: 'POST',
        body: JSON.stringify(body),
      }),
    onSuccess: (form) => replaceFormDraft('recognition', toRecognitionDraft(form)),
  });

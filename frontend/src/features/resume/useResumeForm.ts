import { useEffect } from 'react';

import { useQuery } from '@tanstack/react-query';

import { isServerSession } from '@/lib/accountSession';
import { apiFetch } from '@/lib/api';
import { API_PATHS } from '@/lib/apiPaths';
import { type FormDraft, replaceFormDraft } from '@/lib/formStore';
import { STALE_TIME } from '@/lib/queryConfig';
import { queryKeys } from '@/lib/queryKeys';
import { resumeFromServer } from '@/lib/resumeForm';
import type { components } from '@/types/api.gen';
import type { ResumeDraftRead } from '@/types/resume.types';

type ResumeRead = components['schemas']['ResumeRead'];

/** 서버 초안(2-1.9 JSON)을 양식 저장소 형태로 바꿉니다. `field_states`는 칸 상태, 나머지는 값입니다. */
export const toResumeDraft = (read: ResumeDraftRead): FormDraft => {
  const { field_states, completeness, ...values } = read;
  return { values, fields: field_states, completeness };
};

export const resumePath = (personaId: string) =>
  `/accounts/${encodeURIComponent(personaId)}/resume`;

/**
 * 이력서를 한 번 받아 양식 저장소에 넣습니다. 그 뒤 변화는 대화의 `form_update`가 맡으므로
 * 다시 받아 덮어쓰지 않습니다 (세션이 바뀔 때만 새로 받음).
 * - 모의 세션: `GET /forms/resume`
 * - 실제 서버 세션: `GET /accounts/{id}/resume`을 패널 모양으로 바꿔 넣습니다 (F-15).
 */
export const useResumeForm = (sessionId: string, personaId?: string) => {
  const isServer = isServerSession(sessionId) && !!personaId;
  const query = useQuery({
    queryKey: queryKeys.resumeForm(sessionId),
    queryFn: async () =>
      isServer
        ? resumeFromServer(await apiFetch<ResumeRead>(resumePath(personaId)))
        : apiFetch<ResumeDraftRead>(API_PATHS.LEGACY_RESUME),
    staleTime: STALE_TIME.UNTIL_UPDATED,
    refetchOnWindowFocus: false,
  });

  useEffect(() => {
    if (query.data) replaceFormDraft('resume', toResumeDraft(query.data));
  }, [query.data]);

  return query;
};

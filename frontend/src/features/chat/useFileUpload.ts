import { useMutation } from '@tanstack/react-query';

import { apiUpload } from '@/lib/api';
import { API_PATHS } from '@/lib/apiPaths';
import type { components } from '@/types/api.gen';

type FileCreated = components['schemas']['FileCreated'];

/** 허용 형식 (2-0.4): 사진은 비전 모델, 문서는 파서가 읽습니다. */
export const ACCEPTED_FILE_TYPES = '.jpg,.jpeg,.png,.pdf,.hwp,.hwpx,.docx';

/** 파일 용도 (설계 3.7): 이력서 서류는 판독 뒤 지우고, 구직활동 증빙은 보관해 활동에 연결합니다. */
export const FILE_PURPOSE = { RESUME_DOC: 'resume_doc', EVIDENCE: 'evidence' } as const;
export type FilePurpose = (typeof FILE_PURPOSE)[keyof typeof FILE_PURPOSE];

/** 구직등록(이력서) 단계에서 올린 파일은 이력서 서류, 그 뒤는 구직활동 증빙으로 봅니다. */
export const purposeForStage = (stage: string): FilePurpose =>
  stage === 'job_registration' ? FILE_PURPOSE.RESUME_DOC : FILE_PURPOSE.EVIDENCE;

/** `POST /accounts/{id}/files` → `{ file_id, … }`. 올린 뒤 대화 메시지에 `file_ids`를 붙여 보냅니다. */
export const useFileUpload = (personaId: string, stage: string) =>
  useMutation({
    mutationFn: (file: File) =>
      apiUpload<FileCreated>(API_PATHS.files(personaId), file, {
        purpose: purposeForStage(stage),
      }),
  });

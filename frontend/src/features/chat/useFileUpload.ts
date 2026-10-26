import { useMutation } from '@tanstack/react-query';

import { apiUpload } from '@/lib/api';
import { API_PATHS } from '@/lib/apiPaths';
import { IDEMPOTENCY_HEADER, newIdempotencyKey } from '@/lib/idempotency';
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

/** 구직활동 증빙을 AI 요청 없이도 올리는 단계 (실업인정). 올린 사진은 기록한 활동에 붙습니다. */
const EVIDENCE_STAGE = 'recognition';
export const canAttachEvidenceAt = (stage: string): boolean => stage === EVIDENCE_STAGE;

// 같은 파일을 다시 보내면(재시도·두 번 누름) 같은 키를 써서 한 번만 저장됩니다.
const uploadKeys = new WeakMap<File, string>();
const keyFor = (file: File) => {
  const key = uploadKeys.get(file) ?? newIdempotencyKey();
  uploadKeys.set(file, key);
  return key;
};

/** `POST /accounts/{id}/files` → `{ file_id, … }`. 올린 뒤 대화 메시지에 `file_ids`를 붙여 보냅니다. */
export const useFileUpload = (personaId: string, stage: string) =>
  useMutation({
    mutationFn: (file: File) =>
      apiUpload<FileCreated>(
        API_PATHS.files(personaId),
        file,
        { purpose: purposeForStage(stage) },
        undefined,
        { [IDEMPOTENCY_HEADER]: keyFor(file) },
      ),
  });

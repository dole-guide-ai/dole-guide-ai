import { useMutation } from '@tanstack/react-query';

import { apiUpload } from '@/lib/api';
import { API_PATHS } from '@/lib/apiPaths';
import type { FileUploadRead } from '@/types/chat.types';

/** 허용 형식 (2-0.4): 사진은 비전 모델, 문서는 파서가 읽습니다. */
export const ACCEPTED_FILE_TYPES = '.jpg,.jpeg,.png,.pdf,.hwp,.hwpx,.docx';

/** `POST /files` → `{ file_id, job_id }`. 올린 뒤 대화 메시지에 `file_ids`를 붙여 보냅니다. */
export const useFileUpload = () =>
  useMutation({
    mutationFn: (file: File) => apiUpload<FileUploadRead>(API_PATHS.LEGACY_FILES, file),
  });

import { applyFormUpdate } from '@/lib/formStore';
import { patchSession } from '@/lib/sessionStore';
import type { FormUpdateEvent } from '@/types/chat.types';

/**
 * `form_update`를 저장소에 반영합니다 (2-0.7).
 * `procedure`(단계·회차·다음 기한)는 세션 저장소, 나머지 양식은 양식 저장소로 갑니다.
 */
export const applyFormUpdateEvent = (event: FormUpdateEvent) => {
  if (event.form === 'procedure') {
    if (event.op === 'remove') patchSession(event.path, null);
    else patchSession(event.path, event.value);
    return;
  }
  applyFormUpdate(event);
};

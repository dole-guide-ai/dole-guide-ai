import { sessionFromAccount } from '@/lib/accountSession';
import { apiFetch } from '@/lib/api';
import { API_PATHS } from '@/lib/apiPaths';
import { getSession, setSession } from '@/lib/sessionStore';
import type { components } from '@/types/api.gen';

type AccountRead = components['schemas']['AccountRead'];

/**
 * 계정을 다시 받아 서버가 판정한 값(절차 상태·남은 날·마감·알림)을 세션에 바꿔 끼웁니다.
 * 절차가 바뀌거나(대화의 `procedure` 갱신) 신청서를 낸 뒤 부릅니다. 첫 안내(entry)와 대화는 그대로 둡니다.
 * 실패하면 지금 화면을 그대로 둡니다(다음 새로고침에 다시 받음).
 */
export const refreshAccount = async (personaId: string) => {
  try {
    const fresh = sessionFromAccount(await apiFetch<AccountRead>(API_PATHS.account(personaId)));
    const current = getSession();
    if (current?.persona_id !== personaId) return;
    setSession({ ...current, state: fresh.state, derived: fresh.derived, notices: fresh.notices });
  } catch {
    // 화면은 그대로 두고 다음 새로고침에서 맞춥니다.
  }
};

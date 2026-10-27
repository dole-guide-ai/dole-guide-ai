/**
 * 백엔드의 계정 입장 응답(AccountRead)을 화면이 쓰는 세션 모양(SessionRead)으로 바꾸는 임시 어댑터입니다.
 * 로그인 이후 화면이 아직 예전 세션 구조를 쓰고 있어서 둔 것이며, 화면을 새 API 타입으로 옮기면 지웁니다.
 * 값을 옮겨 담기만 하고 판정(남은 날·마감·신청 경로·알림)은 하지 않습니다. 모두 서버가 계산합니다.
 */

import type { components } from '@/types/api.gen';
import type { BranchId, EntryResult, SessionRead } from '@/types/demo.types';
import type { ImportKind } from '@/types/imports.types';

type AccountRead = components['schemas']['AccountRead'];

const SERVER_SESSION_PREFIX = 'acct-';

export const sessionFromAccount = (account: AccountRead): SessionRead => {
  const { procedure, current_round: round, deadline, entry, today } = account;

  return {
    session_id: `${SERVER_SESSION_PREFIX}${account.persona_id}-${today}`,
    persona_id: account.persona_id,
    state: {
      stage: procedure.stage,
      education_done: procedure.education_done,
      eligibility_applied_date: procedure.eligibility_applied_on ?? null,
      next_recognition_date: round?.recognition_date ?? null,
    },
    derived: {
      current_round: round?.round ?? null,
      d_day: deadline?.d_day ?? null,
      is_overdue: deadline?.overdue ?? false,
      period: round ? { start: round.period_start, end: round.period_end } : null,
      is_attendance_round: round?.attendance_required ?? false,
      can_presubmit_online: procedure.online_presubmit ?? true,
      expected_end_date: procedure.expected_end_date ?? null,
      remaining_rounds: procedure.remaining_rounds ?? null,
      last_round: procedure.last_round ?? null,
      end_reason: procedure.end_reason ?? null,
    },
    notices: account.notices ?? [],
    entry: {
      ...entry,
      branch_id: entry.branch_id as BranchId,
      panel: entry.panel as EntryResult['panel'],
      progress: entry.progress as EntryResult['progress'],
      // 새로고침 전 답을 기다리던 질문이 있으면 그 선택지·불러오기 종류를 다시 띄웁니다 (F-03).
      choices: account.pending_ask?.choices ?? entry.choices,
      pending_ask: account.pending_ask
        ? {
            ...account.pending_ask,
            import_kind: account.pending_ask.import_kind as ImportKind | null,
          }
        : null,
      messages: entry.messages.map(({ template_id, text, cite }) => ({
        template_id,
        text,
        ...(cite ? { cite } : {}),
      })),
    },
  };
};

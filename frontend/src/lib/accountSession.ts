/**
 * 백엔드의 계정 입장 응답(AccountRead)을 화면이 쓰는 세션 모양(SessionRead)으로 바꾸는 임시 어댑터입니다.
 * 로그인 이후 화면이 아직 예전 세션 구조를 쓰고 있어서 둔 것이며, 화면을 새 API 타입으로 옮기면 지웁니다.
 */

import type { components } from '@/types/api.gen';
import type { BranchId, EntryResult, ResumeStatus, SessionRead } from '@/types/demo.types';
import type { ImportKind } from '@/types/imports.types';

type AccountRead = components['schemas']['AccountRead'];

const RESUME_BY_BRANCH: Partial<Record<string, ResumeStatus>> = {
  E7a: 'none',
  E7b: 'outdated',
  E7c: 'draft',
};
// 2026-03-01 이후 수급자격을 신청한 사람부터 2026년 실업인정 안내문 기준을 적용합니다.
const RULE_SET_FROM = '2026-03-01';

const SERVER_SESSION_PREFIX = 'acct-';

/** 실제 백엔드 계정에서 만든 세션인지 (모의 세션 ID는 `mock-`로 시작합니다). */
export const isServerSession = (sessionId: string) => sessionId.startsWith(SERVER_SESSION_PREFIX);

export const sessionFromAccount = (account: AccountRead): SessionRead => {
  const { procedure, current_round: round, entry, today } = account;
  const group = procedure.recipient_group;
  const dDay = round
    ? Math.round((Date.parse(round.recognition_date) - Date.parse(today)) / 86_400_000)
    : null;

  return {
    session_id: `${SERVER_SESSION_PREFIX}${account.persona_id}-${today}`,
    persona_id: account.persona_id,
    state: {
      separation_date: procedure.separation_date,
      age_at_separation: procedure.age_at_separation,
      has_disability: procedure.has_disability,
      recipient_type: group === 'repeat' ? 'repeat' : 'general',
      employment_type: 'regular',
      stage: procedure.stage,
      resume_status: RESUME_BY_BRANCH[entry.branch_id] ?? 'ready',
      education_done: procedure.education_done,
      eligibility_applied_date: procedure.eligibility_applied_on ?? null,
      completed_rounds: round ? round.round - 1 : 0,
      last_recognition_date: null,
      next_recognition_date: round?.recognition_date ?? null,
      demo_today: today,
      demo_time: '10:00',
    },
    derived: {
      rule_group: group === 'repeat' ? 'general' : group,
      rule_set:
        procedure.eligibility_applied_on && procedure.eligibility_applied_on >= RULE_SET_FROM
          ? '2026 안내문 기준'
          : null,
      current_round: round?.round ?? null,
      d_day: dDay,
      period: round ? { start: round.period_start, end: round.period_end } : null,
      is_attendance_round: round?.attendance_required ?? false,
      // 회차 필요 건수는 회차 점검(GET …/rounds/current, F-18)에서 받습니다.
      required: null,
      required_job_search: null,
      can_presubmit_online: procedure.age_at_separation < 65,
      expected_end_date: procedure.expected_end_date ?? null,
      remaining_rounds: procedure.remaining_rounds ?? null,
      last_round: procedure.last_round ?? null,
      end_reason: procedure.end_reason ?? null,
    },
    entry: {
      ...entry,
      branch_id: entry.branch_id as BranchId,
      panel: entry.panel as EntryResult['panel'],
      progress: entry.progress as EntryResult['progress'],
      // 새로고침 전 답을 기다리던 질문이 있으면 그 선택지·불러오기 종류를 다시 띄웁니다 (F-03).
      choices: account.pending_ask?.choices ?? entry.choices,
      pending_ask: account.pending_ask
        ? {
            choices: account.pending_ask.choices,
            import_kind: (account.pending_ask.import_kind as ImportKind | null) ?? null,
            accepts_file: account.pending_ask.accepts_file ?? false,
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

/**
 * 패널 B 회차 할 일(상세기획 2-2)의 임시 타입. 활동 데이터는 2-2.2, 점검 결과는 2-2.12 `check_round` 예시를 따릅니다.
 * 백엔드 API가 올라오면 `pnpm gen:api`로 만든 `api.gen.ts` 타입으로 바꿉니다.
 */

export type ActivityKind = 'job_search' | 'other';

export type ActivityRoute =
  | 'work24'
  | 'portal'
  | 'email'
  | 'company_site'
  | 'newspaper'
  | 'mail'
  | 'fax'
  | 'visit'
  | 'referral'
  | 'interview'
  | 'job_fair'
  | 'training'
  | 'center'
  | 'step_online';

export type ActivitySource = 'conversation' | 'document' | 'work24_import';

/** 2-2.6 계산 결과 */
export type ActivityStatus =
  | 'counted'
  | 'same_day'
  | 'out_of_period'
  | 'not_allowed'
  | 'limit_over'
  | 'needs_check'
  | 'planned';

export interface ActivityEvidence {
  /** 필요 증빙 이름 (2-2.4). 비어 있으면 `증빙 불필요`. */
  required: string[];
  /** 첨부한 파일 이름. 원본은 판독 뒤 지웁니다. */
  attached: string[];
}

/** 이번 회차 활동 한 건 (2-2.2). 배열 안 항목은 `form_update` 경로에서 `item_id`로 가리킵니다. */
export interface RoundActivity {
  item_id: string;
  round: number;
  date: string;
  category: string;
  kind: ActivityKind;
  route: ActivityRoute;
  org_name: string;
  job_title?: string | null;
  evidence: ActivityEvidence;
  source: ActivitySource;
  status: ActivityStatus;
  rule_refs?: string[];
}

export type WarningId = 'W1' | 'W2' | 'W3' | 'W4' | 'W5' | 'W6' | 'W8';

/** 사전 경고 (2-2.7). 문구는 서버가 규칙대로 만들어 보냅니다. */
export interface RoundWarning {
  id: WarningId;
  message: string;
  item_ids: string[];
}

/** 회차 진행 표시 한 칸 (1.9 ⑤): 받은 회차 ✓, 이번 회차 `!`, 출석 회차 `(출석)`. */
export interface RoundMarker {
  round: number;
  state: 'done' | 'current';
  is_attendance: boolean;
}

export type RoundCheckStatus = 'satisfied' | 'short' | 'needs_check';

/** GET /procedure/current-round/check (2-2.12 `check_round` 결과 + 화면에 쓰는 값) */
export interface RoundCheckRead {
  round: number;
  rule_group: string;
  period: { start: string; end: string; days: number };
  required: number | null;
  required_job_search: number | null;
  counted: number;
  counted_job_search: number;
  status: RoundCheckStatus;
  /** 부족한 활동 수와 그중 구직활동 수. 충족이면 0. */
  shortfall: number;
  shortfall_job_search: number;
  activities: RoundActivity[];
  warnings: RoundWarning[];
  round_markers: RoundMarker[];
  /** 규칙표 검수 전이면 `not_verified` (2-2.2) */
  rule_review: 'verified' | 'not_verified';
  cite: string;
  rule_refs: string[];
  /** 대화로 추천을 요청하면 서버가 `form_update`로 true를 보냅니다 (2-2.9 추천 상자). */
  recommendations_open?: boolean;
}

/** 추천 활동 한 건 (2-2.8) */
export interface RecommendationItem {
  recommendation_id: string;
  title: string;
  detail: string;
  kind: ActivityKind;
  evidence_label: string;
  /** 누적 한도가 있는 종류면 사용 현황 (예: `한도 2회 중 0회 사용`) */
  limit_text?: string | null;
  rule_refs: string[];
}

/**
 * PATCH /procedure 본문 (2-0.11): 이용자가 확인한 수정. 추천 `선택`은
 * `{ path: "activities", op: "append", value: { recommendation_id } }`로 예정 활동을 더합니다.
 * 응답은 `FormPatchRead`(적용할 `form_update`들)입니다.
 */
export interface ProcedurePatchCreate {
  path: string;
  op: 'set' | 'append' | 'remove';
  value?: unknown;
}

/** GET /procedure/current-round/recommendations */
export interface RecommendationsRead {
  items: RecommendationItem[];
  /** 권장 기한 문구 (인정일 전날까지) */
  deadline_text: string;
  note: string;
  cite: string;
}

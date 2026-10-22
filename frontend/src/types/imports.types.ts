/**
 * 고용24 불러오기 (모의, 상세기획 2-0.4 · 2-1.5 · 2-2.5). 고용24 `이력보기`·`구직활동 불러오기`를 흉내 내
 * 목록을 보여 주고, 본인이 고른 것만 대화로 보냅니다 (`import_ids`). 한꺼번에 넣지 않습니다.
 * 백엔드 API가 올라오면 `api.gen.ts` 타입으로 바꿉니다.
 */

/** `career-certificate` = 통합경력증명 이력, `work24-activities` = 고용24 입사지원 내역 */
export type ImportKind = 'career-certificate' | 'work24-activities';

export type ImportCategory = 'career' | 'license' | 'training' | 'education' | 'job_search';

export interface ImportItem {
  import_id: string;
  category: ImportCategory;
  title: string;
  detail: string;
  /** 이미 패널에 들어 있는 항목은 다시 고를 수 없습니다. */
  is_recorded: boolean;
}

/** GET /imports/career-certificate · GET /imports/work24-activities */
export interface ImportListRead {
  items: ImportItem[];
  /** 목록 출처 안내 (모의 데이터 표시 포함) */
  source_note: string;
}

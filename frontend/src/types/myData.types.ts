import type { FormUpdateEvent } from '@/types/chat.types';

/**
 * 내 정보 탭 (상세기획 2-0.9). 확정된 값 요약과 절차 상태를 보여 주고, 줄마다 지울 수 있습니다.
 * 백엔드 API가 올라오면 `api.gen.ts` 타입으로 바꿉니다.
 */

export type MyDataGroup = 'resume' | 'procedure' | 'facts';

export interface MyDataItem {
  item_id: string;
  group: MyDataGroup;
  label: string;
  value: string;
  /** 확인한 날짜 (이용자가 답한 사실) */
  confirmed_on?: string | null;
  /** 절차 상태처럼 서비스 진행에 꼭 필요한 줄은 지우지 않습니다. */
  is_deletable: boolean;
}

/** GET /me/data */
export interface MyDataRead {
  items: MyDataItem[];
  /** 저장하지 않는 정보 목록 (2-0.5) */
  not_stored: string[];
}

/** DELETE /me/data 본문: 지울 줄 */
export interface MyDataDelete {
  item_id: string;
}

/** DELETE /me/data 응답: 그 값을 쓰던 패널 칸을 `아직 없음`으로 돌리는 `form_update`들 */
export interface MyDataDeleteRead {
  updates: FormUpdateEvent[];
}

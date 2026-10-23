import { useProcedurePatch } from '@/features/procedure/useProcedurePatch';

/** 활동 빼기 (2-2.11): `PATCH /procedure { path: "activities.{item_id}", op: "remove" }`. */
export const useRemoveActivity = () =>
  useProcedurePatch((itemId: string) => ({ path: `activities.${itemId}`, op: 'remove' }));

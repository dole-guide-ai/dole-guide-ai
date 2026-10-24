'use client';

import { useState } from 'react';

import { Trash2, TriangleAlert } from 'lucide-react';

import { Button } from '@/components/Button';
import { Chip } from '@/components/Chip';
import {
  categoryLabel,
  evidenceChip,
  KIND_LABEL,
  ROUTE_LABEL,
  SOURCE_CHIP,
  STATUS_CHIP,
} from '@/features/procedure/activityLabels';

import { formatShortDate } from '@/lib/dateFormat';
import { ICON_SIZE, ICON_STROKE } from '@/lib/iconSize';
import type { RoundActivity, RoundWarning } from '@/types/procedure.types';

/**
 * 이번 회차 활동 목록 (2-2.9): 날짜 · 회사 · 구분 · 경로 · 칩(계산 결과, 증빙, 출처).
 * 경고(2-2.7)가 걸린 활동은 `주의` 칩을 달고, 목록 아래에 경고 문구를 한 줄씩 보여 줍니다.
 * `빼기`는 한 번 더 물은 뒤 지웁니다 (2-2.11 활동을 빼 달라고 함 → 삭제 후 다시 계산).
 */
interface ActivityListProps {
  activities: RoundActivity[];
  warnings: RoundWarning[];
  onRemove?: (itemId: string) => void;
  isRemoving?: boolean;
}

export const ActivityList = ({
  activities,
  warnings,
  onRemove,
  isRemoving = false,
}: ActivityListProps) => {
  const [confirmingId, setConfirmingId] = useState<string | null>(null);
  const warned = new Set(warnings.flatMap((warning) => warning.item_ids));

  if (activities.length === 0) {
    return <p className="text-muted text-base">아직 기록한 활동이 없어요. 대화로 알려 주세요.</p>;
  }

  return (
    <div className="flex flex-col gap-3">
      <ul className="divide-line divide-y" aria-label="이번 회차 활동">
        {activities.map((activity) => {
          const status = STATUS_CHIP[activity.status];
          const evidence = evidenceChip(activity.evidence);
          const source = SOURCE_CHIP[activity.source];
          const route = ROUTE_LABEL[activity.route];
          const category = categoryLabel(activity.category);
          const meta = [category, KIND_LABEL[activity.kind]].filter(Boolean);
          // 온라인 취업특강처럼 종류와 경로 이름이 같으면 한 번만 씁니다.
          if (route !== category) meta.push(route);
          return (
            <li key={activity.item_id} className="flex flex-col gap-2 py-4">
              <div className="flex items-start gap-3">
                <span className="text-neutral w-20 shrink-0 pt-0.5 text-sm font-semibold">
                  {formatShortDate(activity.date)}
                </span>
                <div className="flex min-w-0 flex-1 flex-col gap-0.5">
                  <span className="text-lg leading-snug font-bold">{activity.org_name}</span>
                  <span className="text-neutral text-sm">{meta.join(' · ')}</span>
                </div>
                {onRemove && confirmingId !== activity.item_id && (
                  <button
                    type="button"
                    onClick={() => setConfirmingId(activity.item_id)}
                    className="text-muted hover:bg-danger-soft hover:text-danger focus-visible:ring-brand inline-flex h-9 shrink-0 items-center gap-1 rounded-lg px-2.5 text-sm font-medium focus-visible:ring-3 focus-visible:outline-hidden"
                    aria-label={`${activity.org_name} 활동 빼기`}
                  >
                    <Trash2 aria-hidden size={ICON_SIZE.sm} strokeWidth={ICON_STROKE} />
                    빼기
                  </button>
                )}
              </div>
              <div className="flex flex-wrap gap-1.5 pl-23">
                <Chip {...status} />
                <Chip
                  {...evidence}
                  title={
                    activity.evidence.required.length
                      ? `필요 증빙: ${activity.evidence.required.join(' + ')}`
                      : undefined
                  }
                />
                <Chip {...source} />
                {warned.has(activity.item_id) && <Chip label="주의" tone="warn" />}
              </div>
              {onRemove && confirmingId === activity.item_id && (
                <div className="bg-neutral-soft ml-23 flex flex-wrap items-center gap-2 rounded-xl px-4 py-3">
                  <span className="text-base">이 활동을 목록에서 뺄까요? 다시 계산해요.</span>
                  <Button
                    variant="secondary"
                    disabled={isRemoving}
                    onClick={() => {
                      onRemove(activity.item_id);
                      setConfirmingId(null);
                    }}
                  >
                    뺄게요
                  </Button>
                  <Button variant="ghost" onClick={() => setConfirmingId(null)}>
                    취소
                  </Button>
                </div>
              )}
            </li>
          );
        })}
      </ul>
      {warnings.length > 0 && (
        <ul className="bg-warn-soft flex flex-col gap-1.5 rounded-xl px-4 py-3" aria-label="경고">
          {warnings.map((warning) => (
            <li key={warning.id} className="text-warn flex items-start gap-2 text-sm font-medium">
              <TriangleAlert
                aria-hidden
                size={ICON_SIZE.sm}
                strokeWidth={ICON_STROKE}
                className="mt-0.5 shrink-0"
              />
              {warning.message}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
};

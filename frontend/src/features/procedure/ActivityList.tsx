import { Chip } from '@/components/Chip';
import {
  evidenceChip,
  KIND_LABEL,
  ROUTE_LABEL,
  SOURCE_CHIP,
  STATUS_CHIP,
} from '@/features/procedure/activityLabels';

import { formatShortDate } from '@/lib/dateFormat';
import type { RoundActivity, RoundWarning } from '@/types/procedure.types';

/**
 * 이번 회차 활동 목록 (2-2.9): 날짜 · 회사 · 구분 · 경로 · 칩(계산 결과, 증빙, 출처).
 * 경고(2-2.7)가 걸린 활동은 `주의` 칩을 달고, 목록 아래에 경고 문구를 한 줄씩 보여 줍니다.
 */
interface ActivityListProps {
  activities: RoundActivity[];
  warnings: RoundWarning[];
}

export const ActivityList = ({ activities, warnings }: ActivityListProps) => {
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
          const meta = [activity.category, KIND_LABEL[activity.kind]];
          // 온라인 취업특강처럼 종류와 경로 이름이 같으면 한 번만 씁니다.
          if (route !== activity.category) meta.push(route);
          return (
            <li key={activity.item_id} className="flex flex-col gap-1.5 py-3">
              <div className="flex flex-wrap items-baseline gap-x-2">
                <span className="font-semibold">{formatShortDate(activity.date)}</span>
                <span className="text-lg font-bold">{activity.org_name}</span>
                <span className="text-muted text-sm">{meta.join(' · ')}</span>
              </div>
              <div className="flex flex-wrap gap-1.5">
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
            </li>
          );
        })}
      </ul>
      {warnings.length > 0 && (
        <ul className="flex flex-col gap-1" aria-label="경고">
          {warnings.map((warning) => (
            <li key={warning.id} className="bg-warn-soft text-warn rounded-lg px-3 py-2 text-sm">
              {warning.message}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
};

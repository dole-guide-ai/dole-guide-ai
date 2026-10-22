'use client';

import { useState } from 'react';

import { Button } from '@/components/Button';
import { Chip } from '@/components/Chip';
import { EvidenceLine } from '@/components/EvidenceLine';
import { KIND_LABEL } from '@/features/procedure/activityLabels';
import { usePlanActivity } from '@/features/procedure/usePlanActivity';
import { useRecommendations } from '@/features/procedure/useRecommendations';

import { ApiError } from '@/lib/api';

/**
 * 부족한 활동 추천 상자 (2-2.8 · 시안 2-2-1 ④⑤): 최대 3개, 구분·증빙·한도 칩, 권장 기한, 공고는 직접 고른다는 안내.
 * `선택`을 누르면 그 활동이 예정(`planned`)으로 목록에 들어가고, 한 번 고른 추천은 다시 누를 수 없습니다.
 */
interface RecommendationBoxProps {
  sessionId: string;
  plannedIds: string[];
  /** 실제 서버 세션이면 계정 추천 API를 씁니다 (F-19). */
  personaId?: string;
}

const errorText = (error: unknown, fallback: string) =>
  error instanceof ApiError ? error.message : fallback;

export const RecommendationBox = ({ sessionId, plannedIds, personaId }: RecommendationBoxProps) => {
  const query = useRecommendations(sessionId, true, personaId);
  const plan = usePlanActivity(sessionId, personaId);
  // 서버가 만든 예정 활동 ID는 추천 ID와 달라서, 이번 화면에서 고른 추천을 따로 기억합니다.
  const [pickedIds, setPickedIds] = useState<string[]>([]);

  if (query.isPending) return <p className="text-muted text-base">추천을 고르는 중…</p>;
  if (query.isError) {
    return (
      <p role="alert" className="text-danger text-base">
        {errorText(query.error, '추천을 불러오지 못했어요.')}
      </p>
    );
  }

  const { items, deadline_text, note, cite } = query.data;

  return (
    <section
      className="border-brand/30 bg-brand-soft/40 flex flex-col gap-3 rounded-2xl border p-4"
      aria-label="추천 활동"
    >
      <h3 className="text-lg font-bold">이렇게 채워 보세요</h3>
      <ol className="flex flex-col gap-2">
        {items.map((item, index) => {
          const isPlanned =
            plannedIds.includes(`planned_${item.recommendation_id}`) ||
            pickedIds.includes(item.recommendation_id);
          return (
            <li
              key={item.recommendation_id}
              className="bg-surface flex flex-wrap items-center justify-between gap-3 rounded-xl px-4 py-3"
            >
              <div className="flex flex-col gap-1">
                <p className="text-base font-bold">
                  {index + 1}. {item.title}
                </p>
                <p className="text-muted text-sm">{item.detail}</p>
                <div className="flex flex-wrap gap-1.5">
                  <Chip label={KIND_LABEL[item.kind]} tone="info" />
                  <Chip
                    label={item.evidence_label}
                    tone={item.evidence_label === '증빙 불필요' ? 'neutral' : 'warn'}
                  />
                  {item.limit_text && <Chip label={item.limit_text} tone="neutral" />}
                </div>
              </div>
              <Button
                variant="secondary"
                onClick={() =>
                  plan.mutate(item.recommendation_id, {
                    onSuccess: () => setPickedIds((ids) => [...ids, item.recommendation_id]),
                  })
                }
                disabled={isPlanned || plan.isPending}
                aria-label={`${item.title} 선택`}
              >
                {isPlanned ? '선택함' : '선택'}
              </Button>
            </li>
          );
        })}
      </ol>
      {plan.isError && (
        <p role="alert" className="text-danger text-sm">
          {errorText(plan.error, '예정 활동으로 넣지 못했어요.')}
        </p>
      )}
      <p className="text-base">{deadline_text}</p>
      <p className="text-muted text-sm">{note}</p>
      <EvidenceLine cite={cite} />
    </section>
  );
};

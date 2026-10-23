'use client';

import { useState } from 'react';

import { Button } from '@/components/Button';
import { EvidenceLine } from '@/components/EvidenceLine';
import { ActivityList } from '@/features/procedure/ActivityList';
import { DdayCard } from '@/features/procedure/DdayCard';
import { RecommendationBox } from '@/features/procedure/RecommendationBox';
import { RequirementCard } from '@/features/procedure/RequirementCard';
import { RoundProgress } from '@/features/procedure/RoundProgress';
import { useRemoveActivity } from '@/features/procedure/useRemoveActivity';
import { useRoundCheck } from '@/features/procedure/useRoundCheck';
import { useRoundDraft } from '@/features/procedure/useRoundDraft';

import { ApiError } from '@/lib/api';
import { formatKoreanDate } from '@/lib/dateFormat';
import type { SessionRead } from '@/types/demo.types';

/**
 * 패널 B 이번 회차 할 일 (2-2.9): D-day 카드 · 필요 활동 카드 · 회차 진행 · 활동 목록 · 경고 · 추천 상자 · 신청서 버튼.
 * 점검 결과는 서버 `check_round` 값을 양식 저장소에서 읽고, 대화의 `form_update`(form: "activities")로 갱신됩니다.
 */
interface RoundPanelProps {
  session: SessionRead;
  /** `활동 정리 끝 · 신청서 만들기` (부족하면 한 번 물은 뒤). 신청서 화면(2-3)으로 넘어가는 대화를 보냅니다. */
  onOpenForm?: () => void;
}

export const RoundPanel = ({ session, onOpenForm }: RoundPanelProps) => {
  const query = useRoundCheck(session.session_id, session.derived.current_round);
  const draft = useRoundDraft();
  const [isAskingShort, setIsAskingShort] = useState(false);
  const remove = useRemoveActivity();

  if (query.isPending) return <p className="text-muted text-base">이번 회차 활동을 불러오는 중…</p>;
  if (query.isError) {
    return (
      <p role="alert" className="text-danger text-base">
        {query.error instanceof ApiError
          ? query.error.message
          : '이번 회차 활동을 불러오지 못했어요.'}
      </p>
    );
  }

  // 저장소가 아직 채워지기 전(첫 렌더) 에는 받은 응답을 그대로 씁니다.
  const check = { ...query.data, ...draft };
  const isOverdue = (session.derived.d_day ?? 0) < 0;
  const plannedIds = check.activities
    .filter((activity) => activity.status === 'planned')
    .map((activity) => activity.item_id);

  const handleOpenForm = () => {
    if (check.shortfall > 0 && !isAskingShort) {
      setIsAskingShort(true);
      return;
    }
    setIsAskingShort(false);
    onOpenForm?.();
  };

  return (
    <div className="flex flex-col gap-4">
      {/* E2 (1.6): 인정일이 지났으면 변경 신청 안내를 맨 위에 둡니다 (DUE-089, DUE-094). */}
      {isOverdue && session.state.next_recognition_date && (
        <div role="alert" className="bg-danger-soft text-danger rounded-xl px-4 py-3">
          <p className="text-base font-semibold">
            {formatKoreanDate(session.state.next_recognition_date)} 실업인정일이 지났어요.
          </p>
          <p className="text-base">
            날짜를 착각했거나 개인 사정이었다면 인정일부터 14일 안에 고용센터에 가서 변경 신청을 할
            수 있어요(수급기간 중 1회). 활동 기록은 계속할 수 있어요.
          </p>
        </div>
      )}
      <DdayCard state={session.state} derived={session.derived} />
      <RequirementCard check={check} />
      <RoundProgress markers={check.round_markers} />

      <section className="flex flex-col gap-2">
        <h3 className="text-base font-bold">이번 회차 활동</h3>
        <ActivityList
          activities={check.activities}
          warnings={check.warnings}
          onRemove={(itemId) => remove.mutate(itemId)}
          isRemoving={remove.isPending}
        />
        {remove.isError && (
          <p role="alert" className="text-danger text-sm">
            {remove.error instanceof ApiError ? remove.error.message : '활동을 빼지 못했어요.'}
          </p>
        )}
      </section>

      {check.recommendations_open && (
        <RecommendationBox sessionId={session.session_id} plannedIds={plannedIds} />
      )}

      <div className="flex flex-col gap-2">
        {isAskingShort ? (
          <div
            role="alertdialog"
            aria-label="부족한 채로 신청서 열기"
            className="bg-warn-soft flex flex-col gap-2 rounded-xl px-4 py-3"
          >
            <p className="text-warn text-base font-semibold">
              아직 {check.shortfall}건 부족해요. 그래도 신청서를 볼까요?
            </p>
            <div className="flex flex-wrap gap-2">
              <Button onClick={handleOpenForm}>그래도 볼게요</Button>
              <Button variant="secondary" onClick={() => setIsAskingShort(false)}>
                활동 더 채울게요
              </Button>
            </div>
          </div>
        ) : (
          <Button size="lg" onClick={handleOpenForm} disabled={!onOpenForm}>
            활동 정리 끝 · 신청서 만들기
          </Button>
        )}
      </div>

      <div className="flex flex-col gap-1">
        {check.rule_review === 'not_verified' && (
          <p className="text-muted text-sm">
            검수 전 규칙으로 계산했어요. 최종 인정 여부는 관할 고용센터가 판단해요.
          </p>
        )}
        <EvidenceLine cite={check.cite} />
      </div>
    </div>
  );
};

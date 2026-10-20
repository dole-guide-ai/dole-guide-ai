import type { RoundCheckRead } from '@/types/procedure.types';

/**
 * 필요 활동 카드 (2-2.9 · 시안 2-2-1 ②): 필요 건수(구직활동 최소) 대비 인정 건수.
 * 부족이면 주황 "인정 n건 · m건 더", 충족이면 초록 "인정 n건 · 충족". 숫자는 서버 계산 결과만 씁니다.
 */
interface RequirementCardProps {
  check: Pick<
    RoundCheckRead,
    | 'round'
    | 'required'
    | 'required_job_search'
    | 'counted'
    | 'counted_job_search'
    | 'status'
    | 'shortfall'
    | 'shortfall_job_search'
  >;
}

export const RequirementCard = ({ check }: RequirementCardProps) => {
  const { round, required, required_job_search, counted, counted_job_search, status } = check;
  const isSatisfied = status === 'satisfied';
  const isUnknown = status === 'needs_check' || required === null;

  const requirementText = isUnknown
    ? '필요 횟수는 고용센터 안내를 따라 주세요'
    : `활동 ${required}건${required_job_search ? ` · 그중 구직활동 ${required_job_search}건` : ''}`;

  const resultText = isUnknown
    ? '확인 필요'
    : isSatisfied
      ? `인정 ${counted}건 · 충족`
      : `인정 ${counted}건 · ${check.shortfall}건 더`;

  const toneClass = isSatisfied
    ? 'border-ok/30 bg-ok-soft text-ok'
    : 'border-warn/30 bg-warn-soft text-warn';

  return (
    <div className={`flex flex-col gap-1 rounded-2xl border px-5 py-4 ${toneClass}`}>
      <p className="text-ink text-sm">
        {round}차 필요 활동 · {requirementText}
      </p>
      <p className="text-2xl font-bold" aria-label="필요 활동 결과">
        {resultText}
      </p>
      {!isUnknown && (
        <p className="text-ink text-sm">
          인정된 구직활동 {counted_job_search}건
          {check.shortfall_job_search > 0 && ` · 구직활동 ${check.shortfall_job_search}건 더 필요`}
        </p>
      )}
    </div>
  );
};

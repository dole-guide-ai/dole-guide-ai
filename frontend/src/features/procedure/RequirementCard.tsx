import { PERCENT_SCALE } from '@/lib/panelLayout';
import type { RoundCheckRead } from '@/types/procedure.types';

/**
 * 필요 활동 카드 (2-2.9 · 시안 2-2-1 ②): 필요 건수(구직활동 최소) 대비 인정 건수.
 * 부족이면 주황 "인정 n건 · m건 더", 충족이면 초록 "인정 n건 · 충족"과 채움 막대. 숫자는 서버 계산 결과만 씁니다.
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

  const isCountable = !isUnknown && required !== null && required > 0;
  const percent = isCountable ? Math.min(PERCENT_SCALE, (counted / required) * PERCENT_SCALE) : 0;
  const toneText = isSatisfied ? 'text-ok' : 'text-warn';

  return (
    <section aria-label="필요 활동" className="flex flex-col gap-2">
      <p className="text-neutral text-sm font-medium">
        {round}차 필요 활동 · {requirementText}
      </p>
      <p className={`text-2xl font-bold ${toneText}`} aria-label="필요 활동 결과">
        {resultText}
      </p>
      {isCountable && (
        <div
          role="progressbar"
          aria-label="필요 활동 채움"
          aria-valuemin={0}
          aria-valuemax={required}
          aria-valuenow={Math.min(counted, required)}
          className="bg-neutral-soft h-2 overflow-hidden rounded-full"
        >
          <div
            className={`h-full rounded-full transition-[width] duration-500 ${isSatisfied ? 'bg-ok' : 'bg-warn'}`}
            style={{ width: `${percent}%` }}
          />
        </div>
      )}
      {!isUnknown && (
        <p className="text-neutral text-sm">
          인정된 구직활동 {counted_job_search}건
          {check.shortfall_job_search > 0 && ` · 구직활동 ${check.shortfall_job_search}건 더 필요`}
        </p>
      )}
    </section>
  );
};

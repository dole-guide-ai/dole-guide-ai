import { usePastApplication } from '@/features/procedure/usePastRounds';

import { ApiError } from '@/lib/api';
import { formatShortDate } from '@/lib/dateFormat';

interface PastRoundApplicationProps {
  personaId: string;
  round: number;
}

/** 지난 회차 신청서 요약 (읽기 전용, F-04): 대상기간·제출 상태·구직활동 줄·구직 외 활동. */
export const PastRoundApplication = ({ personaId, round }: PastRoundApplicationProps) => {
  const query = usePastApplication(personaId, round);

  if (query.isPending) return <p className="text-muted text-base">신청서를 불러오는 중…</p>;
  if (query.isError) {
    return (
      <p role="alert" className="text-danger text-base">
        {query.error instanceof ApiError ? query.error.message : '신청서를 불러오지 못했어요.'}
      </p>
    );
  }

  const app = query.data;
  return (
    <div className="flex flex-col gap-2 text-base">
      <p>
        대상기간 {formatShortDate(app.period_start)} ~ {formatShortDate(app.period_end)} · 인정일{' '}
        {formatShortDate(app.recognition_date)}
      </p>
      <p className="font-semibold">{app.status === 'submitted' ? '제출함' : '제출 기록 없음'}</p>
      {app.job_search_rows.length > 0 ? (
        <ul className="flex flex-col gap-1">
          {app.job_search_rows.map((row) => (
            <li key={row.activity_id}>
              {formatShortDate(row.activity_date)} · {row.company_name ?? '사업장 미정'}
              {row.application_method ? ` · ${row.application_method}` : ''}
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-muted">구직활동 기록이 없어요.</p>
      )}
      {app.other_rows.length > 0 && (
        <p className="text-muted">구직 외 활동 {app.other_rows.length}건</p>
      )}
    </div>
  );
};

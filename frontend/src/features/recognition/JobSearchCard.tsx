import { Chip } from '@/components/Chip';
import { RequiredMark } from '@/components/RequiredMark';
import { activityEvidenceChip } from '@/features/recognition/recognitionLabels';

import { formatShortDate } from '@/lib/dateFormat';
import { fieldChip } from '@/lib/fieldChip';
import type { FieldMeta } from '@/lib/formStore';
import type { JobSearchActivity } from '@/types/recognition.types';

/**
 * 구직활동내역 한 건 (2-3.2): 고용24 10칸 중 서비스가 받는 칸 + 첨부. 사업장 이메일·전화번호는 받지 않아
 * `고용24에서` 직접 적는다고 표시합니다 (2-0.5). 비어 있는 ★칸은 2-3.4 질문으로 채웁니다.
 */
interface JobSearchCardProps {
  activity: JobSearchActivity;
  meta?: FieldMeta;
}

export const JobSearchCard = ({ activity, meta }: JobSearchCardProps) => {
  const chip = fieldChip(meta ?? { status: 'extracted', source: activity.source });
  const rows: [string, string | null, boolean][] = [
    ['구직활동일', formatShortDate(activity.activity_date), true],
    ['사업체명', activity.company_name, true],
    ['인사담당자(담당부서)', activity.recruitment_contact, true],
    ['모집 직종', activity.recruitment_occupation, true],
    ['보수 수준', activity.salary_level, false],
    ['구직 방법', activity.job_search_method, true],
    ['응모 방식', activity.application_method, true],
    ['활동 결과', activity.activity_result, true],
  ];

  return (
    <article
      className="bg-neutral-soft/60 flex flex-col gap-3 rounded-xl px-5 py-4"
      aria-label={`구직활동 ${activity.company_name}`}
    >
      <div className="flex flex-wrap items-center gap-2">
        <h4 className="text-lg font-bold">
          {formatShortDate(activity.activity_date)} {activity.company_name}
        </h4>
        <Chip {...chip} />
        <Chip {...activityEvidenceChip(activity)} />
      </div>
      <dl className="grid grid-cols-1 gap-x-6 gap-y-2 text-sm sm:grid-cols-2">
        {rows.map(([label, value, isRequired]) => (
          <div key={label} className="flex gap-2">
            <dt className="text-muted w-32 shrink-0">
              {label}
              {isRequired && <RequiredMark />}
            </dt>
            <dd className={value ? 'text-ink' : 'text-warn font-semibold'}>
              {value ?? (isRequired ? '답변 필요' : '없음')}
            </dd>
          </div>
        ))}
        <div className="flex gap-2 sm:col-span-2">
          <dt className="text-muted w-32 shrink-0">사업장 이메일·전화</dt>
          <dd className="text-muted">고용24에서 직접 (선택 칸)</dd>
        </div>
      </dl>
    </article>
  );
};

import { Chip } from '@/components/Chip';

import { fieldChip } from '@/lib/fieldChip';
import type { OtherActivity } from '@/types/recognition.types';

/**
 * 구직활동 외 활동사항 한 건 (2-3.2): 과정★ · 세부내역★ · 첨부. 과정은 고용24 `과정` 선택지 이름(2-2.3)입니다.
 * 외부 4시간 이상 특강·집단상담처럼 서비스가 과정을 고르지 않는 활동은 고용24에서 고르라고 안내합니다.
 */
interface OtherActivityCardProps {
  activity: OtherActivity;
}

export const OtherActivityCard = ({ activity }: OtherActivityCardProps) => {
  const chip = fieldChip({ status: 'extracted', source: activity.source });
  const rows: [string, string | null][] = [
    ['과정', activity.course],
    ['세부내역', activity.details],
  ];

  return (
    <article
      className="border-line flex flex-col gap-2 rounded-xl border px-4 py-3"
      aria-label={`구직 외 활동 ${activity.course ?? '과정 미정'}`}
    >
      <div className="flex flex-wrap items-center gap-2">
        <h4 className="text-base font-bold">{activity.course ?? '과정은 고용24에서 골라요'}</h4>
        <Chip {...chip} />
        <Chip label={activity.attachment_ids.length ? '증빙 있음' : '첨부 없음'} tone="neutral" />
      </div>
      <dl className="flex flex-col gap-1 text-sm">
        {rows.map(([label, value]) => (
          <div key={label} className="flex gap-2">
            <dt className="text-muted w-32 shrink-0">
              {label}
              <span className="text-warn ml-0.5">★</span>
            </dt>
            <dd className={value ? 'text-ink' : 'text-warn font-semibold'}>
              {value ?? (label === '과정' ? '고용24에서 해당 과정을 골라 주세요' : '답변 필요')}
            </dd>
          </div>
        ))}
      </dl>
    </article>
  );
};

import type { ReactNode } from 'react';

import { Chip } from '@/components/Chip';

import { type ChipSpec, fieldChip } from '@/lib/fieldChip';
import type { FieldMeta } from '@/lib/formStore';

/**
 * 패널 칸 한 줄: 이름 · 값 · 칩 · 근거 보기 · 고치기 (2-0.6).
 * 값이 없으면 `아직 없음`으로 보이고, 근거는 서류 이름이나 대화 날짜·짧은 인용을 한 줄로 보여 줍니다.
 */
interface FieldRowProps {
  label: string;
  value?: ReactNode;
  meta?: FieldMeta;
  /** 고용24 ★ 필수 칸 */
  isRequired?: boolean;
  /** 저장 상태와 무관하게 고정 칩을 쓸 때 (예: `고용24에서`) */
  chip?: ChipSpec;
  onEdit?: () => void;
}

const evidenceText = (meta?: FieldMeta) => {
  const evidence = meta?.evidence;
  if (!evidence) return null;
  const parts = [
    evidence.kind === 'utterance' ? `대화 ${evidence.date ?? ''}`.trim() : evidence.kind,
    evidence.quote ? `“${evidence.quote}”` : null,
    evidence.note,
  ].filter(Boolean);
  return parts.join(' · ');
};

export const FieldRow = ({ label, value, meta, isRequired, chip, onEdit }: FieldRowProps) => {
  const spec = chip ?? fieldChip(meta);
  const isEmpty = value === null || value === undefined || value === '';
  const evidence = evidenceText(meta);

  return (
    <div className="flex flex-col gap-1 py-2">
      <div className="flex flex-wrap items-start gap-x-3 gap-y-1">
        <dt className="text-muted w-28 shrink-0 text-sm">
          {label}
          {isRequired && (
            <span className="text-warn ml-0.5" aria-label="필수">
              ★
            </span>
          )}
        </dt>
        <dd className={`min-w-0 flex-1 text-base ${isEmpty ? 'text-muted' : 'text-ink'}`}>
          {isEmpty ? '아직 없음' : value}
        </dd>
        <Chip label={spec.label} tone={spec.tone} />
        {onEdit && (
          <button
            type="button"
            onClick={onEdit}
            className="text-brand focus-visible:ring-brand/40 text-sm font-medium hover:underline focus-visible:ring-3 focus-visible:outline-hidden"
          >
            고치기
          </button>
        )}
      </div>
      {evidence && (
        <details className="text-muted pl-31 text-sm">
          <summary className="cursor-pointer select-none">근거 보기</summary>
          <p className="mt-1">{evidence}</p>
        </details>
      )}
    </div>
  );
};

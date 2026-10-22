'use client';

import { type ReactNode, useState } from 'react';

import { Chip } from '@/components/Chip';

import { ApiError } from '@/lib/api';
import { type ChipSpec, fieldChip } from '@/lib/fieldChip';
import type { FieldMeta } from '@/lib/formStore';

/**
 * 패널 칸 한 줄: 이름 · 값 · 칩 · 근거 보기 · 고치기 · 직접 입력 (2-0.6).
 * 값이 없으면 `아직 없음`으로 보이고, 근거는 서류 이름이나 대화 날짜·짧은 인용을 한 줄로 보여 줍니다.
 * 직접 입력은 서버 값 정리를 거치며, 형식이 안 맞으면 칸 아래에 이유가 남습니다.
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
  /** 패널에서 직접 고치기. 글자 칸에만 둡니다. 실패하면 ApiError를 던집니다. */
  onDirectSave?: (value: string) => Promise<unknown>;
  /** 직접 입력 칸의 시작 값 (value가 ReactNode라 따로 받음) */
  rawValue?: string | null;
  /** 직접 입력 방식: 글(기본) · 숫자 · 고용24 선택지 (시연 개선 8번) */
  inputKind?: 'text' | 'number' | 'select';
  /** `select`일 때 고용24 화면의 선택지 */
  options?: readonly string[];
  /** 글 칸 입력 예시 (예: 2004-03 ~ 2026-09) */
  placeholder?: string;
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

const INPUT_CLASS =
  'border-line focus-visible:border-brand focus-visible:ring-brand/40 min-w-40 flex-1 rounded-lg border px-3 py-1.5 text-base focus-visible:ring-3 focus-visible:outline-hidden';

const LINK_CLASS =
  'text-sm font-medium text-brand hover:underline focus-visible:ring-3 focus-visible:ring-brand/40 focus-visible:outline-hidden disabled:text-muted';

export const FieldRow = ({
  label,
  value,
  meta,
  isRequired,
  chip,
  onEdit,
  onDirectSave,
  rawValue,
  inputKind = 'text',
  options = [],
  placeholder,
}: FieldRowProps) => {
  const [draft, setDraft] = useState<string | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  const isEmpty = value === null || value === undefined || value === '';
  // 값은 있는데 저장 상태가 없는 칸(예: 직종 이름)은 '아직 없음' 칩을 달지 않습니다 (PPT 점검 N1).
  const spec = chip ?? (meta || isEmpty ? fieldChip(meta) : null);
  // '없어요'로 답한 칸은 '아직 없음'이 아니라 '없음'으로 보입니다 (PPT 점검 N2).
  const emptyText = meta?.status === 'not_applicable' ? '없음' : '아직 없음';
  const evidence = evidenceText(meta);
  const isEditing = draft !== null;

  const handleSave = async () => {
    if (!onDirectSave || draft === null) return;
    setIsSaving(true);
    setSaveError(null);
    try {
      await onDirectSave(draft.trim());
      setDraft(null);
    } catch (error) {
      setSaveError(error instanceof ApiError ? error.message : '저장하지 못했어요.');
    } finally {
      setIsSaving(false);
    }
  };

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
        {isEditing ? (
          <dd className="flex min-w-0 flex-1 flex-wrap items-center gap-2">
            {inputKind === 'select' ? (
              <select
                value={draft}
                onChange={(event) => setDraft(event.target.value)}
                disabled={isSaving}
                aria-label={`${label} 직접 입력`}
                className={INPUT_CLASS}
              >
                <option value="" disabled>
                  골라 주세요
                </option>
                {options.map((option) => (
                  <option key={option} value={option}>
                    {option}
                  </option>
                ))}
              </select>
            ) : (
              <input
                type={inputKind === 'number' ? 'number' : 'text'}
                inputMode={inputKind === 'number' ? 'numeric' : undefined}
                value={draft}
                placeholder={placeholder}
                onChange={(event) => setDraft(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === 'Enter' && !event.nativeEvent.isComposing) void handleSave();
                  if (event.key === 'Escape') setDraft(null);
                }}
                disabled={isSaving}
                aria-label={`${label} 직접 입력`}
                className={INPUT_CLASS}
              />
            )}
            <button
              type="button"
              onClick={() => void handleSave()}
              disabled={isSaving}
              className={LINK_CLASS}
            >
              {isSaving ? '저장 중…' : '저장'}
            </button>
            <button
              type="button"
              onClick={() => setDraft(null)}
              disabled={isSaving}
              className={LINK_CLASS}
            >
              취소
            </button>
          </dd>
        ) : (
          <dd className={`min-w-0 flex-1 text-base ${isEmpty ? 'text-muted' : 'text-ink'}`}>
            {isEmpty ? emptyText : value}
          </dd>
        )}
        {spec && <Chip label={spec.label} tone={spec.tone} />}
        {!isEditing && onEdit && (
          <button type="button" onClick={onEdit} className={LINK_CLASS}>
            고치기
          </button>
        )}
        {!isEditing && onDirectSave && (
          <button type="button" onClick={() => setDraft(rawValue ?? '')} className={LINK_CLASS}>
            직접 입력
          </button>
        )}
      </div>
      {saveError && (
        <p role="alert" className="text-danger pl-31 text-sm">
          {saveError}
        </p>
      )}
      {evidence && (
        <details className="text-muted pl-31 text-sm">
          <summary className="cursor-pointer select-none">근거 보기</summary>
          <p className="mt-1">{evidence}</p>
        </details>
      )}
    </div>
  );
};

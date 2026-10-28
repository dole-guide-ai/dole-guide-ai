'use client';

import { useState } from 'react';

import { EXPERIENCE_TYPES } from '@/features/resume/resumeLabels';

import { ApiError } from '@/lib/api';
import type { FirstOccupation } from '@/types/resume.types';

/** 희망 직종 경력여부 직접 입력: 신입 / 경력 n년 n개월 (고용24 희망조건 ★). */
interface ExperienceEditorProps {
  current: FirstOccupation;
  onSave: (type: string, years: number | null, months: number | null) => Promise<unknown>;
  onClose: () => void;
}

const MONTHS_IN_YEAR = 12;

const FIELD_CLASS =
  'border-line focus-visible:border-accent focus-visible:ring-brand rounded-lg border px-3 py-1.5 text-base focus-visible:ring-3 focus-visible:outline-hidden';
const LINK_CLASS =
  'inline-flex h-9 items-center rounded-lg px-2.5 text-sm font-semibold text-brand hover:bg-brand-soft focus-visible:ring-3 focus-visible:ring-brand focus-visible:outline-hidden disabled:text-muted';

const asNumber = (text: string) => (text.trim() === '' ? null : Number(text));

export const ExperienceEditor = ({ current, onSave, onClose }: ExperienceEditorProps) => {
  const [type, setType] = useState(current.experience_type ?? EXPERIENCE_TYPES[0]);
  const [years, setYears] = useState(String(current.experience_years ?? ''));
  const [months, setMonths] = useState(String(current.experience_months ?? ''));
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const isExperienced = type === EXPERIENCE_TYPES[0];

  const save = async () => {
    setIsSaving(true);
    setError(null);
    try {
      await onSave(
        type,
        isExperienced ? asNumber(years) : null,
        isExperienced ? asNumber(months) : null,
      );
      onClose();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : '저장하지 못했어요.');
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="flex w-full flex-col gap-2">
      <div className="flex flex-wrap items-center gap-2">
        <select
          aria-label="경력여부"
          value={type}
          onChange={(event) => setType(event.target.value)}
          disabled={isSaving}
          className={FIELD_CLASS}
        >
          {EXPERIENCE_TYPES.map((t) => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
        </select>
        {isExperienced && (
          <>
            <input
              type="number"
              inputMode="numeric"
              min={0}
              aria-label="경력 연수"
              value={years}
              onChange={(event) => setYears(event.target.value)}
              disabled={isSaving}
              className={`${FIELD_CLASS} w-20`}
            />
            년
            <input
              type="number"
              inputMode="numeric"
              min={0}
              max={MONTHS_IN_YEAR - 1}
              aria-label="경력 개월"
              value={months}
              onChange={(event) => setMonths(event.target.value)}
              disabled={isSaving}
              className={`${FIELD_CLASS} w-20`}
            />
            개월
          </>
        )}
        <button
          type="button"
          className={LINK_CLASS}
          disabled={isSaving}
          onClick={() => void save()}
        >
          {isSaving ? '저장 중…' : '저장'}
        </button>
        <button type="button" className={LINK_CLASS} disabled={isSaving} onClick={onClose}>
          취소
        </button>
      </div>
      {error && (
        <p role="alert" className="text-danger text-sm">
          {error}
        </p>
      )}
    </div>
  );
};

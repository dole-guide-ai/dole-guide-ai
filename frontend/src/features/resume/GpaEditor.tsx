'use client';

import { useState } from 'react';

import { GPA_SCALES } from '@/features/resume/resumeLabels';

import { ApiError } from '@/lib/api';

/** 학점/총점 직접 입력: 학점은 숫자, 총점(만점)은 고용24 드롭다운 값. 만점을 넘는지는 서버가 봅니다. */
interface GpaEditorProps {
  gpa: string | null;
  scale: string | null;
  onSave: (gpa: string, scale: string) => Promise<unknown>;
  onClose: () => void;
}

const FIELD_CLASS =
  'border-line focus-visible:border-accent focus-visible:ring-brand rounded-lg border px-3 py-1.5 text-base focus-visible:ring-3 focus-visible:outline-hidden';
const LINK_CLASS =
  'inline-flex h-9 items-center rounded-lg px-2.5 text-sm font-semibold text-brand hover:bg-brand-soft focus-visible:ring-3 focus-visible:ring-brand focus-visible:outline-hidden disabled:text-muted';

export const GpaEditor = ({ gpa, scale, onSave, onClose }: GpaEditorProps) => {
  const [score, setScore] = useState(gpa ?? '');
  const [max, setMax] = useState(scale ?? '');
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const save = async () => {
    setIsSaving(true);
    setError(null);
    try {
      await onSave(score.trim(), max);
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
        <input
          type="text"
          inputMode="decimal"
          aria-label="학점"
          placeholder="3.8"
          value={score}
          onChange={(event) => setScore(event.target.value)}
          disabled={isSaving}
          className={`${FIELD_CLASS} w-24`}
        />
        /
        <select
          aria-label="총점"
          value={max}
          onChange={(event) => setMax(event.target.value)}
          disabled={isSaving}
          className={FIELD_CLASS}
        >
          <option value="" disabled>
            만점
          </option>
          {GPA_SCALES.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
        <button
          type="button"
          className={LINK_CLASS}
          disabled={isSaving || !score.trim() || !max}
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

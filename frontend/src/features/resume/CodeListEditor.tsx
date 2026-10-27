'use client';

import { useState } from 'react';

import { X } from 'lucide-react';

import { CodeSearch } from '@/features/resume/CodeSearch';
import { RegionSelect } from '@/features/resume/RegionSelect';
import { namedCodeText, occupationText, regionText } from '@/features/resume/resumeLabels';
import type { SearchKind } from '@/features/resume/useWork24Codes';

import { ApiError } from '@/lib/api';
import { ICON_SIZE, ICON_STROKE } from '@/lib/iconSize';
import type { CodeChoice, CodeRef } from '@/types/resume.types';

/**
 * 공통코드 칸(희망직종·희망근무지역·경력 직종)의 직접 입력. 고른 목록을 칩으로 보여 주고 빼거나
 * 드롭다운으로 더한 뒤 한 번에 저장합니다. 이름·상태와 개수 한도는 서버가 다시 봅니다.
 * 대화에서 말만 하고 아직 고르지 않은 값(`needs_confirmation`)은 목록에서 다시 골라야 저장됩니다.
 */
interface CodeListEditorProps {
  kind: SearchKind | 'region';
  current: CodeRef[];
  /** 고를 수 있는 개수 (고용24 희망 직종·지역 3개, 경력 직종 1개) */
  max: number;
  onSave: (choices: CodeChoice[]) => Promise<unknown>;
  onClose: () => void;
}

interface Picked {
  choice: CodeChoice | null;
  label: string;
}

const LINK_CLASS =
  'inline-flex h-9 items-center gap-1 rounded-lg px-2.5 text-sm font-semibold text-brand hover:bg-brand-soft focus-visible:ring-3 focus-visible:ring-brand focus-visible:outline-hidden disabled:text-muted disabled:hover:bg-transparent';

const labelOf = (ref: CodeRef, kind: CodeListEditorProps['kind']) => {
  if (kind === 'region') return regionText(ref);
  if (kind === 'occupation') return occupationText(ref);
  return namedCodeText(ref.name, ref, kind);
};

const fromRef = (ref: CodeRef, kind: CodeListEditorProps['kind']): Picked => {
  const label = labelOf(ref, kind) ?? ref.name;
  if (ref.status === 'needs_confirmation') return { choice: null, label };
  return { choice: ref.code ? { code: ref.code } : { name: ref.name }, label };
};

export const CodeListEditor = ({ kind, current, max, onSave, onClose }: CodeListEditorProps) => {
  const [items, setItems] = useState<Picked[]>(() => current.map((ref) => fromRef(ref, kind)));
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const unpicked = items.some((item) => !item.choice);

  const add = (choice: CodeChoice, label: string) =>
    setItems((prev) => [...prev, { choice, label }]);
  const save = async () => {
    setIsSaving(true);
    setError(null);
    try {
      await onSave(items.flatMap((item) => (item.choice ? [item.choice] : [])));
      onClose();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : '저장하지 못했어요.');
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="flex w-full flex-col gap-2">
      {items.length > 0 && (
        <ul className="flex flex-wrap gap-2" aria-label="고른 값">
          {items.map((item, index) => (
            <li
              key={`${item.label}-${index}`}
              className={`flex items-center gap-1 rounded-full border px-3 py-1 text-sm ${item.choice ? 'border-line' : 'border-warn text-warn'}`}
            >
              {item.label}
              <button
                type="button"
                aria-label={`${item.label} 빼기`}
                disabled={isSaving}
                onClick={() => setItems((prev) => prev.filter((_, i) => i !== index))}
              >
                <X aria-hidden size={ICON_SIZE.sm} strokeWidth={ICON_STROKE} />
              </button>
            </li>
          ))}
        </ul>
      )}
      {unpicked && (
        <p className="text-warn text-sm">
          확인 필요 표시가 붙은 값은 빼고 목록에서 다시 골라 주세요.
        </p>
      )}
      {items.length < max &&
        (kind === 'region' ? (
          <RegionSelect onPick={add} disabled={isSaving} />
        ) : (
          <CodeSearch kind={kind} onPick={add} disabled={isSaving} />
        ))}
      <div className="flex gap-2">
        <button
          type="button"
          className={LINK_CLASS}
          disabled={isSaving || unpicked}
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

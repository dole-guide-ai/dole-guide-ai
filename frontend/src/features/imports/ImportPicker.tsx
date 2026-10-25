'use client';

import { useState } from 'react';

import { Button } from '@/components/Button';
import { Chip } from '@/components/Chip';
import { Spinner } from '@/components/Spinner';
import { useImportList } from '@/features/imports/useImportList';

import { ApiError } from '@/lib/api';
import type { ImportCategory, ImportKind } from '@/types/imports.types';

/**
 * 고용24 불러오기 고르기 (2-0.4 · 2-1.5 · 2-2.5). 고용24 `이력보기`처럼 목록을 보여 주고 본인이 고른 것만 넣습니다.
 * 도현 실측("기억에 없는 무언가 튀어나옴") 때문에 한꺼번에 넣지 않고, 처음에는 아무것도 고르지 않은 상태로 엽니다.
 */
interface ImportPickerProps {
  kind: ImportKind;
  sessionId: string;
  personaId: string;
  isDisabled?: boolean;
  onApply: (importIds: string[]) => void;
}

const CATEGORY_LABEL: Record<ImportCategory, string> = {
  career: '경력',
  license: '자격',
  training: '직업훈련',
  education: '교육',
  job_search: '입사지원',
};

const TITLE: Record<ImportKind, string> = {
  'career-certificate': '통합경력증명 이력',
  'work24-activities': '고용24 입사지원 내역',
};

export const ImportPicker = ({
  kind,
  sessionId,
  personaId,
  isDisabled = false,
  onApply,
}: ImportPickerProps) => {
  const query = useImportList(kind, sessionId, personaId);
  const [selected, setSelected] = useState<string[]>([]);

  if (query.isPending) return <Spinner label="불러올 내역을 찾는 중…" size="md" />;
  if (query.isError) {
    return (
      <p role="alert" className="text-danger text-sm">
        {query.error instanceof ApiError ? query.error.message : '내역을 불러오지 못했어요.'}
      </p>
    );
  }

  const toggle = (id: string) =>
    setSelected((current) =>
      current.includes(id) ? current.filter((value) => value !== id) : [...current, id],
    );

  return (
    <section
      aria-label={`${TITLE[kind]} 고르기`}
      className="border-brand-soft bg-surface flex flex-col gap-3 rounded-2xl border p-4"
    >
      <div>
        <p className="text-base font-bold">{TITLE[kind]}</p>
        <p className="text-muted text-sm">{query.data.source_note}</p>
      </div>
      {query.data.items.length === 0 ? (
        <p className="text-muted text-base">불러올 내역이 없어요. 말로 알려 주셔도 돼요.</p>
      ) : (
        <ul className="flex flex-col gap-2">
          {query.data.items.map((item) => (
            <li key={item.import_id}>
              <label
                className={`flex items-start gap-3 rounded-xl border px-3 py-2 ${
                  item.is_recorded ? 'border-line bg-canvas' : 'border-line hover:border-brand'
                }`}
              >
                <input
                  type="checkbox"
                  className="mt-1 size-5"
                  checked={selected.includes(item.import_id)}
                  onChange={() => toggle(item.import_id)}
                  disabled={item.is_recorded || isDisabled}
                />
                <span className="flex min-w-0 flex-1 flex-col">
                  <span className="flex flex-wrap items-center gap-2">
                    <span className="text-base font-semibold">{item.title}</span>
                    <Chip label={CATEGORY_LABEL[item.category]} tone="info" />
                    {item.is_recorded && <Chip label="이미 넣음" tone="neutral" />}
                  </span>
                  <span className="text-muted text-sm">{item.detail}</span>
                </span>
              </label>
            </li>
          ))}
        </ul>
      )}
      <Button onClick={() => onApply(selected)} disabled={selected.length === 0 || isDisabled}>
        {selected.length ? `고른 ${selected.length}건 넣기` : '넣을 항목을 골라 주세요'}
      </Button>
    </section>
  );
};

'use client';

import { useId, useState } from 'react';

import { CODE_KIND_LABEL } from '@/features/resume/resumeLabels';
import { type SearchKind, useCodeSearch } from '@/features/resume/useWork24Codes';

import type { CodeChoice } from '@/types/resume.types';

/**
 * 고용24 공통코드 찾기 드롭다운(직종·자격면허·전공). 이름 일부를 치면 서버가 찾은 후보(대화와 같은
 * 기준)가 뜨고, 고르면 코드를, 맞는 게 없으면 "이름만 적기"로 이름을 넘깁니다. 코드는 서버가 다시 봅니다.
 */
interface CodeSearchProps {
  kind: SearchKind;
  onPick: (choice: CodeChoice, label: string) => void;
  disabled?: boolean;
}

const INPUT_CLASS =
  'border-line focus-visible:border-accent focus-visible:ring-brand w-full rounded-lg border px-3 py-1.5 text-base focus-visible:ring-3 focus-visible:outline-hidden';
const OPTION_CLASS =
  'hover:bg-brand-soft focus-visible:bg-brand-soft w-full rounded-md px-3 py-2 text-left text-base focus-visible:outline-hidden';

export const CodeSearch = ({ kind, onPick, disabled }: CodeSearchProps) => {
  const label = CODE_KIND_LABEL[kind];
  const [text, setText] = useState('');
  const listId = useId();
  const search = useCodeSearch(kind, text);
  const typed = text.trim();
  const hits = search.data ?? [];

  const pick = (choice: CodeChoice, label: string) => {
    onPick(choice, label);
    setText('');
  };

  return (
    <div className="flex w-full flex-col gap-1">
      <input
        type="text"
        role="combobox"
        aria-expanded={typed.length > 0}
        aria-controls={listId}
        aria-label={`고용24 ${label} 찾기`}
        placeholder={`${label} 이름 일부`}
        value={text}
        onChange={(event) => setText(event.target.value)}
        disabled={disabled}
        className={INPUT_CLASS}
      />
      {typed && (
        <ul
          id={listId}
          role="listbox"
          aria-label={`고용24 ${label} 후보`}
          className="border-line max-h-60 overflow-y-auto rounded-lg border p-1"
        >
          {hits.map((code) => (
            <li key={code.code} role="option" aria-selected={false}>
              <button
                type="button"
                className={OPTION_CLASS}
                onClick={() => pick({ code: code.code }, code.name)}
              >
                {code.name}
              </button>
            </li>
          ))}
          {search.isSuccess && hits.length === 0 && (
            <li className="text-muted px-3 py-2 text-sm">고용24 {label} 목록에서 찾지 못했어요.</li>
          )}
          <li role="option" aria-selected={false}>
            <button
              type="button"
              className={`${OPTION_CLASS} text-brand font-semibold`}
              onClick={() => pick({ name: typed }, `${typed} (이름만 적기)`)}
            >
              ‘{typed}’ 이름만 적기
            </button>
          </li>
        </ul>
      )}
      {search.isError && (
        <p role="alert" className="text-danger text-sm">
          {label} 목록을 불러오지 못했어요.
        </p>
      )}
    </div>
  );
};

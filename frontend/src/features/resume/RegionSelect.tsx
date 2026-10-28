'use client';

import { useState } from 'react';

import { useRegionCodes } from '@/features/resume/useWork24Codes';

import type { CodeChoice } from '@/types/resume.types';

/**
 * 고용24 근무지역 고르기: 시·도 → 시·군·구 두 단계 드롭다운. 시·군·구는 고르지 않아도 되고, 그러면
 * 시·도 전체(예: 서울)를 고릅니다. 코드가 맞는지는 서버가 다시 봅니다.
 */
interface RegionSelectProps {
  onPick: (choice: CodeChoice, label: string) => void;
  disabled?: boolean;
}

const SELECT_CLASS =
  'border-line focus-visible:border-accent focus-visible:ring-brand min-w-36 flex-1 rounded-lg border px-3 py-1.5 text-base focus-visible:ring-3 focus-visible:outline-hidden';
const ADD_CLASS =
  'text-brand hover:bg-brand-soft focus-visible:ring-brand disabled:text-muted inline-flex h-9 items-center rounded-lg px-2.5 text-sm font-semibold focus-visible:ring-3 focus-visible:outline-hidden disabled:hover:bg-transparent';

export const RegionSelect = ({ onPick, disabled }: RegionSelectProps) => {
  const regions = useRegionCodes();
  const [province, setProvince] = useState('');
  const [district, setDistrict] = useState('');
  const codes = regions.data ?? [];
  const provinces = codes.filter((c) => c.depth === 1);
  const districts = codes.filter((c) => c.parent === province);
  const target = district || province;
  const chosen = codes.find((c) => c.code === target);

  if (regions.isError) {
    return (
      <p role="alert" className="text-danger text-sm">
        지역 목록을 불러오지 못했어요.
      </p>
    );
  }
  return (
    <div className="flex w-full flex-wrap items-center gap-2">
      <select
        aria-label="시·도"
        value={province}
        onChange={(event) => {
          setProvince(event.target.value);
          setDistrict('');
        }}
        disabled={disabled || regions.isPending}
        className={SELECT_CLASS}
      >
        <option value="">시·도</option>
        {provinces.map((c) => (
          <option key={c.code} value={c.code}>
            {c.name}
          </option>
        ))}
      </select>
      {districts.length > 0 && (
        <select
          aria-label="시·군·구"
          value={district}
          onChange={(event) => setDistrict(event.target.value)}
          disabled={disabled}
          className={SELECT_CLASS}
        >
          <option value="">시·군·구 (전체)</option>
          {districts.map((c) => (
            <option key={c.code} value={c.code}>
              {c.name}
            </option>
          ))}
        </select>
      )}
      <button
        type="button"
        className={ADD_CLASS}
        disabled={disabled || !chosen}
        onClick={() => {
          if (!chosen) return;
          onPick({ code: chosen.code }, chosen.name);
          setProvince('');
          setDistrict('');
        }}
      >
        추가
      </button>
    </div>
  );
};

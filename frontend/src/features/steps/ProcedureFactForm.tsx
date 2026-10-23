'use client';

import { useState } from 'react';

import { Button } from '@/components/Button';
import {
  type ProcedureFact,
  useAccountReload,
  useProcedurePatch,
} from '@/features/steps/useProcedurePatch';

import { ApiError } from '@/lib/api';

/**
 * 패널 E·Q·1차 인정일 화면에서 고용센터에서 받은 사실을 직접 넣는 입력 (F-16).
 * 날짜 칸이 있으면 날짜와 함께, 없으면 버튼 한 번으로 `PATCH …/procedure`를 보냅니다.
 * 대화로 알려도 되지만 버튼으로도 넣을 수 있게 둡니다 (F-16 열린 질문: 이수 확인은 버튼으로 결정).
 */
interface ProcedureFactFormProps {
  personaId: string;
  path: ProcedureFact['path'];
  buttonLabel: string;
  /** 날짜를 받으면 칸 이름. 없으면 버튼만 (교육 이수) */
  dateLabel?: string;
  defaultDate?: string;
  hint?: string;
}

export const ProcedureFactForm = ({
  personaId,
  path,
  buttonLabel,
  dateLabel,
  defaultDate = '',
  hint,
}: ProcedureFactFormProps) => {
  const patch = useProcedurePatch(personaId);
  const reload = useAccountReload(personaId);
  const [date, setDate] = useState(defaultDate);
  const needsDate = Boolean(dateLabel);
  // 저장은 됐는데 화면만 못 바꿨으면 같은 사실을 다시 보내지 않고 다시 불러오기만 권합니다.
  const isSavedNotReloaded = patch.data?.reloaded === false && !reload.isSuccess;
  const canSubmit = !patch.isPending && !isSavedNotReloaded && (!needsDate || date !== '');

  const handleSubmit = () => {
    const fact = (needsDate ? { path, value: date } : { path, value: true }) as ProcedureFact;
    patch.mutate(fact);
  };

  return (
    <div className="border-brand/30 bg-brand-soft/40 flex flex-col gap-3 rounded-2xl border px-5 py-4">
      {hint && <p className="text-base">{hint}</p>}
      <div className="flex flex-wrap items-end gap-3">
        {needsDate && (
          <label className="flex flex-col gap-1 text-base font-semibold">
            {dateLabel}
            <input
              type="date"
              value={date}
              onChange={(event) => setDate(event.target.value)}
              className="border-line focus-visible:border-brand focus-visible:ring-brand/40 rounded-xl border px-3 py-2 text-base font-normal focus-visible:ring-3 focus-visible:outline-hidden"
            />
          </label>
        )}
        <Button onClick={handleSubmit} disabled={!canSubmit}>
          {patch.isPending ? '저장하는 중…' : buttonLabel}
        </Button>
      </div>
      {isSavedNotReloaded && (
        <div role="alert" className="flex flex-wrap items-center gap-2 text-base">
          <p className="text-warn">
            {reload.error instanceof ApiError
              ? reload.error.message
              : '저장했어요. 화면을 새로 불러오지 못했어요.'}
          </p>
          <Button variant="secondary" onClick={() => reload.mutate()} disabled={reload.isPending}>
            화면 다시 불러오기
          </Button>
        </div>
      )}
      {patch.isError && (
        <p role="alert" className="text-danger text-base">
          {patch.error instanceof ApiError
            ? patch.error.message
            : '저장하지 못했어요. 다시 시도해 주세요.'}
        </p>
      )}
    </div>
  );
};

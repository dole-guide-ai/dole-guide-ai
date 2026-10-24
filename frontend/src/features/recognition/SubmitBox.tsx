'use client';

import { useState } from 'react';

import { Button } from '@/components/Button';
import {
  ATTEND_ITEM_LABEL,
  CHECKLIST_LABEL,
  SUBMIT_MODE_TEXT,
} from '@/features/recognition/recognitionLabels';

import type { AttendItem, ChecklistItem, SubmitMode } from '@/types/recognition.types';

/**
 * 제출 전 확인 + 제출 버튼 (2-3.6). 막는 항목(`blocking`)이 남았으면 버튼이 꺼지고, 경고 항목은 표시만 합니다.
 * 출석 회차는 준비물(신분증·수급자격증)을 체크해야 버튼이 켜집니다. 낼 수 있는지는 서버 `can_submit`을 따릅니다.
 */
interface SubmitBoxProps {
  mode: SubmitMode;
  recognitionDate: string;
  checklist: ChecklistItem[];
  attendItems: AttendItem[];
  canSubmit: boolean;
  isSubmitting: boolean;
  isDone: boolean;
  onSubmit: () => void;
}

export const SubmitBox = ({
  mode,
  recognitionDate,
  checklist,
  attendItems,
  canSubmit,
  isSubmitting,
  isDone,
  onSubmit,
}: SubmitBoxProps) => {
  const [checked, setChecked] = useState<AttendItem[]>([]);
  const text = SUBMIT_MODE_TEXT[mode];
  const isAttend = mode === 'attend';
  const hasAllItems = !isAttend || attendItems.every((item) => checked.includes(item));
  const remaining = checklist.filter((item) => item.blocking && !item.done);
  const isEnabled = canSubmit && text.isActionable && hasAllItems && !isSubmitting && !isDone;

  const toggle = (item: AttendItem) =>
    setChecked((current) =>
      current.includes(item) ? current.filter((value) => value !== item) : [...current, item],
    );

  return (
    <section
      className="bg-canvas flex flex-col gap-3 rounded-2xl px-4 py-4"
      aria-label="제출 전 확인"
    >
      <h3 className="text-base font-bold">제출 전 확인</h3>
      <ul className="grid grid-cols-1 gap-1 text-sm sm:grid-cols-2">
        {checklist.map((item) => (
          <li
            key={item.key}
            className={
              item.done ? 'text-ok' : item.blocking ? 'text-warn font-semibold' : 'text-muted'
            }
          >
            {item.done ? '완료' : item.blocking ? '남음' : '주의'} · {CHECKLIST_LABEL[item.key]}
          </li>
        ))}
      </ul>

      {isAttend && (
        <fieldset className="flex flex-wrap gap-4">
          <legend className="text-muted mb-1 text-sm">출석 준비물</legend>
          {attendItems.map((item) => (
            <label key={item} className="flex items-center gap-2 text-base">
              <input
                type="checkbox"
                className="size-5"
                checked={checked.includes(item)}
                onChange={() => toggle(item)}
                disabled={isDone}
              />
              {ATTEND_ITEM_LABEL[item]}
            </label>
          ))}
        </fieldset>
      )}

      <p className="text-base">{text.guide(recognitionDate)}</p>
      <Button size="lg" onClick={onSubmit} disabled={!isEnabled}>
        {isDone ? '확인했어요 (모의)' : isSubmitting ? '확인하는 중…' : text.button}
      </Button>
      {!isDone && remaining.length > 0 && (
        <p className="text-muted text-sm">
          남은 것: {remaining.map((item) => CHECKLIST_LABEL[item.key]).join(', ')}
        </p>
      )}
      {!isDone && remaining.length === 0 && !hasAllItems && (
        <p className="text-muted text-sm">준비물을 챙겼는지 체크해 주세요.</p>
      )}
      {/* PROC-080·081: 전송 뒤 처리 상태 확인, 회수해서 고치면 다시 전송 */}
      {isDone && mode === 'send' && (
        <p className="bg-brand-soft text-brand rounded-xl px-4 py-3 text-base">
          고용24 마이페이지 → 민원처리현황에서 신청 완료가 됐는지 꼭 확인해 주세요. 신청서를
          회수해서 고쳤다면 반드시 다시 전송해야 해요.
        </p>
      )}
    </section>
  );
};

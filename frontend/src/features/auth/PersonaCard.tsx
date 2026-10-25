import { Check } from 'lucide-react';

import { PERSONA_HIGHLIGHTS } from '@/features/auth/personaHighlights';
import type { PersonaCardRead } from '@/features/auth/usePersonas';

import { ICON_SIZE, ICON_STROKE_BOLD } from '@/lib/iconSize';

/** 가상 계정 카드 (1.4 ②). 카드 어디를 눌러도 같은 동작입니다. */
interface PersonaCardProps {
  persona: PersonaCardRead;
  onSelect: (personaId: string) => void;
  isDisabled?: boolean;
}

export const PersonaCard = ({ persona, onSelect, isDisabled = false }: PersonaCardProps) => {
  const { name, age, job, quote, summary } = persona.display;
  // 버튼 이름은 "{이름} 계정으로 시작"으로 짧게 두고, 나이·직종·한마디·상태 요약·해 볼 수 있는 일은 설명으로 읽게 합니다.
  const descriptionId = `persona-${persona.persona_id}-description`;
  const highlights = PERSONA_HIGHLIGHTS[persona.persona_id] ?? [];

  return (
    <button
      type="button"
      disabled={isDisabled}
      onClick={() => onSelect(persona.persona_id)}
      aria-label={`${name} 계정으로 시작`}
      aria-describedby={descriptionId}
      className="border-line bg-surface hover:border-brand focus-visible:ring-brand flex h-full w-full flex-col rounded-2xl border p-5 text-left break-keep shadow-xs transition hover:shadow-sm focus-visible:ring-3 focus-visible:outline-hidden disabled:cursor-wait disabled:opacity-60"
    >
      <span id={descriptionId} className="flex min-w-0 flex-col gap-3">
        <span className="flex items-center gap-3">
          <span
            className="bg-brand-soft text-brand flex size-12 shrink-0 items-center justify-center rounded-full text-xl font-bold"
            aria-hidden
          >
            {name.charAt(0)}
          </span>
          <span className="flex min-w-0 flex-col">
            <span className="text-xl font-bold">{name}</span>
            <span className="text-muted text-base">
              {age}세 · {job}
            </span>
          </span>
        </span>
        <span className="text-ink text-base">“{quote}”</span>
        <span className="bg-neutral-soft text-neutral inline-flex w-fit rounded-full px-3 py-1 text-sm font-medium">
          {summary}
        </span>
        {/* 버튼 안이라 목록 요소(ul) 대신 span으로 줄을 나눕니다. */}
        {highlights.length > 0 && (
          <span className="border-line flex flex-col gap-1.5 border-t pt-3">
            <span className="text-muted text-sm font-semibold">이 계정으로 해 볼 수 있어요</span>
            {highlights.map((highlight) => (
              <span key={highlight} className="text-ink flex items-start gap-2 text-base">
                <Check
                  aria-hidden
                  size={ICON_SIZE.sm}
                  strokeWidth={ICON_STROKE_BOLD}
                  className="text-brand mt-1 shrink-0"
                />
                {highlight}
              </span>
            ))}
          </span>
        )}
      </span>
    </button>
  );
};

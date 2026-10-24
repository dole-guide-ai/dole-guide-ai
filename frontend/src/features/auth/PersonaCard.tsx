import type { PersonaCardRead } from '@/features/auth/usePersonas';

/** 가상 계정 카드 (1.4 ②). 카드 어디를 눌러도 같은 동작입니다. */
interface PersonaCardProps {
  persona: PersonaCardRead;
  onSelect: (personaId: string) => void;
  isDisabled?: boolean;
}

export const PersonaCard = ({ persona, onSelect, isDisabled = false }: PersonaCardProps) => {
  const { name, age, job, quote, summary } = persona.display;
  // 버튼 이름은 "{이름} 계정으로 시작"으로 짧게 두고, 나이·직종·한마디·상태 요약은 설명으로 읽게 합니다.
  const descriptionId = `persona-${persona.persona_id}-description`;

  return (
    <button
      type="button"
      disabled={isDisabled}
      onClick={() => onSelect(persona.persona_id)}
      aria-label={`${name} 계정으로 시작`}
      aria-describedby={descriptionId}
      className="border-line bg-surface hover:border-brand focus-visible:ring-brand flex w-full items-start gap-4 rounded-2xl border p-5 text-left shadow-xs transition hover:shadow-sm focus-visible:ring-3 focus-visible:outline-hidden disabled:cursor-wait disabled:opacity-60"
    >
      <span
        className="bg-brand-soft text-brand flex size-14 shrink-0 items-center justify-center rounded-full text-2xl font-bold"
        aria-hidden
      >
        {name.charAt(0)}
      </span>
      <span id={descriptionId} className="flex min-w-0 flex-col gap-2">
        <span className="text-xl font-bold">
          {name}
          <span className="text-muted ml-2 text-base font-normal">
            {age}세 · {job}
          </span>
        </span>
        <span className="text-ink text-base">“{quote}”</span>
        <span className="bg-neutral-soft text-neutral inline-flex w-fit rounded-full px-3 py-1 text-sm font-medium">
          {summary}
        </span>
      </span>
    </button>
  );
};

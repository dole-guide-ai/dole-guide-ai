/**
 * 선택지 버튼 (최대 3개, 1.7 문구 원칙). 진입 응답의 `choices`와 `ask_user` 이벤트를 같은 모양으로 처리합니다 (1.11).
 */
interface ChoiceButtonsProps {
  choices: string[];
  onSelect: (choice: string) => void;
  isDisabled?: boolean;
}

export const ChoiceButtons = ({ choices, onSelect, isDisabled = false }: ChoiceButtonsProps) => {
  if (choices.length === 0) return null;

  return (
    <div role="group" aria-label="선택지" className="flex flex-wrap gap-2">
      {choices.map((choice) => (
        <button
          key={choice}
          type="button"
          disabled={isDisabled}
          onClick={() => onSelect(choice)}
          className="border-brand bg-surface text-brand hover:bg-brand-soft focus-visible:ring-brand/40 disabled:border-line disabled:text-muted rounded-full border px-4 py-2 text-base font-medium transition focus-visible:ring-3 focus-visible:outline-hidden disabled:cursor-not-allowed"
        >
          {choice}
        </button>
      ))}
    </div>
  );
};

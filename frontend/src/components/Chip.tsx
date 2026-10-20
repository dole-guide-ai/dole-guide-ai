export type ChipTone = 'info' | 'ok' | 'warn' | 'neutral';

/** 패널 칩 (2-0.6). 파랑 = 서류·불러오기, 초록 = 확정, 주황 = 확인 필요, 회색 = 자동·없음. */
interface ChipProps {
  label: string;
  tone: ChipTone;
  title?: string;
}

const TONE_CLASS: Record<ChipTone, string> = {
  info: 'bg-info-soft text-info',
  ok: 'bg-ok-soft text-ok',
  warn: 'bg-warn-soft text-warn',
  neutral: 'bg-neutral-soft text-neutral',
};

export const Chip = ({ label, tone, title }: ChipProps) => (
  <span
    title={title}
    className={`inline-flex shrink-0 items-center rounded-full px-2.5 py-0.5 text-xs font-semibold whitespace-nowrap ${TONE_CLASS[tone]}`}
  >
    {label}
  </span>
);

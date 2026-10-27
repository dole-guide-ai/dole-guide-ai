import type { Notice } from '@/types/demo.types';

/**
 * 패널 안 주의 상자. 무엇을 알릴지와 문구는 서버(`AccountRead.notices`)가 정하고 여기서는 보여 주기만 합니다.
 * 인정일 지남처럼 바로 해야 할 일은 `danger`, 신청 경로 같은 안내는 `warn`으로 그립니다.
 */
interface NoticeBoxProps {
  notice: Notice;
  tone?: 'warn' | 'danger';
  children?: React.ReactNode;
}

const TONE_CLASS = {
  warn: 'border-warn bg-warn-soft',
  danger: 'border-danger bg-danger-soft',
} as const;

const TITLE_CLASS = { warn: 'text-warn', danger: 'text-danger' } as const;

export const NoticeBox = ({ notice, tone = 'warn', children }: NoticeBoxProps) => (
  <div
    role={tone === 'danger' ? 'alert' : undefined}
    className={`flex flex-col gap-2 rounded-xl border px-4 py-3 ${TONE_CLASS[tone]}`}
  >
    <p className={`text-base font-semibold ${TITLE_CLASS[tone]}`}>{notice.title}</p>
    <p className="text-base">{notice.text}</p>
    {children}
  </div>
);

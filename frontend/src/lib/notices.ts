import type { Notice } from '@/types/demo.types';

/** 서버 알림 종류(`NoticeKind`). 문구·판정은 서버가 정하고 화면은 종류로 놓을 자리만 고릅니다. */
export const NOTICE_KIND = {
  VISIT: 'visit',
  OVERDUE: 'overdue',
  ATTEND: 'attend',
} as const satisfies Record<string, Notice['kind']>;

export const findNotice = (notices: Notice[], kind: Notice['kind']) =>
  notices.find((notice) => notice.kind === kind);

'use client';

import { useState } from 'react';

import { Button } from '@/components/Button';
import type { SessionNotice } from '@/features/dashboard/sessionNotices';

/**
 * 주의 사항 토스트 (시연 개선 6번): 패널 안 주의 상자를 처음 한 번만 오른쪽 아래에 띄웁니다.
 * 닫은 알림은 이 화면에서 다시 띄우지 않습니다. 고령층을 생각해 저절로 사라지지 않고 `확인`으로 닫습니다.
 */
interface NoticeToastProps {
  notices: SessionNotice[];
}

export const NoticeToast = ({ notices }: NoticeToastProps) => {
  const [seen, setSeen] = useState<string[]>([]);
  const notice = notices.find((item) => !seen.includes(item.key));
  if (!notice) return null;

  return (
    <div
      role="status"
      className="border-warn bg-surface from-warn-soft to-warn-soft fixed right-6 bottom-4 z-40 flex max-w-sm flex-col gap-2 rounded-2xl border bg-linear-to-b p-4 shadow-lg lg:top-32 lg:bottom-auto"
    >
      <p className="text-warn text-base font-bold">{notice.title}</p>
      <p className="text-base">{notice.text}</p>
      <Button
        variant="secondary"
        className="self-end"
        onClick={() => setSeen((current) => [...current, notice.key])}
      >
        확인
      </Button>
    </div>
  );
};

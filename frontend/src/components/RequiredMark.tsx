import { Asterisk } from 'lucide-react';

import { ICON_SIZE, ICON_STROKE_BOLD } from '@/lib/iconSize';

/** 필수 칸 표시. 눈으로는 주황 별표 아이콘, 스크린리더는 "필수"로 읽습니다. */
export const RequiredMark = () => (
  <span className="text-warn relative ml-0.5 inline-flex align-top">
    <Asterisk aria-hidden size={ICON_SIZE.sm} strokeWidth={ICON_STROKE_BOLD} />
    <span className="sr-only">필수</span>
  </span>
);

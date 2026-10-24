/**
 * 오른쪽 패널 공용 배치. 패널 스크롤 칸(PanelFrame)의 안쪽 여백(px-6 · lg:px-8 · py-6)을 거꾸로 당겨
 * 머리·발 줄이 패널 가장자리까지 닿게 합니다. 패널 여백을 바꾸면 여기도 같이 바꿉니다.
 */
export const STICKY_HEADER =
  'bg-surface/90 border-line sticky -top-6 z-10 -mx-6 flex flex-col gap-2 border-b px-6 py-3 backdrop-blur lg:-mx-8 lg:px-8';

export const STICKY_FOOTER =
  'bg-surface/90 border-line sticky -bottom-6 z-10 -mx-6 -mb-6 flex flex-col gap-2 border-t px-6 py-3 backdrop-blur lg:-mx-8 lg:px-8';

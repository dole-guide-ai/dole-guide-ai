export const ALLOWED_ELEMENTS = ['p', 'strong', 'em', 'ol', 'ul', 'li', 'br'];

const EMPHASIS = '**';

/**
 * 스트리밍 중에 아직 닫히지 않은 마지막 `**`를 뺍니다. "**구직등"이 기호째 보였다가
 * 굵게로 바뀌며 깜빡이지 않게 합니다. 닫히면 원래대로 굵게 그려집니다.
 */
export const trimOpenEmphasis = (text: string): string => {
  const count = text.split(EMPHASIS).length - 1;
  if (count % 2 === 0) return text;
  const last = text.lastIndexOf(EMPHASIS);
  return text.slice(0, last) + text.slice(last + EMPHASIS.length);
};

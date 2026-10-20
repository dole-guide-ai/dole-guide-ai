'use client';

import { Button } from '@/components/Button';
import { useBigText } from '@/features/bigText/useBigText';

/**
 * 켜져 있으면 `글자 보통`, 꺼져 있으면 `글자 크게`가 보입니다 (1.9 시안 1-3 ①).
 * 문구가 다음 동작을 말해 주므로 `aria-pressed`는 함께 쓰지 않습니다(낭독이 겹침).
 */
export const BigTextToggle = () => {
  const { isBig, toggle } = useBigText();

  return (
    <Button variant="secondary" onClick={toggle}>
      {isBig ? '글자 보통' : '글자 크게'}
    </Button>
  );
};

'use client';

import { Button } from '@/components/Button';
import { useBigText } from '@/features/bigText/useBigText';

/** 켜져 있으면 `글자 보통`, 꺼져 있으면 `글자 크게`가 보입니다 (1.9 시안 1-3 ①). */
export const BigTextToggle = () => {
  const { isBig, toggle } = useBigText();

  return (
    <Button variant="secondary" onClick={toggle} aria-pressed={isBig}>
      {isBig ? '글자 보통' : '글자 크게'}
    </Button>
  );
};

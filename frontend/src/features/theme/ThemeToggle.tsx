'use client';

import { Moon, Sun } from 'lucide-react';

import { Button } from '@/components/Button';
import { useTheme } from '@/features/theme/useTheme';

import { ICON_SIZE, ICON_STROKE } from '@/lib/iconSize';

/** 헤더의 밝게·어둡게 바꾸기. `글자 크게`처럼 다음 동작을 문구로 보여 줍니다. */
export const ThemeToggle = () => {
  const { isDark, toggle } = useTheme();
  const Icon = isDark ? Sun : Moon;

  return (
    <Button variant="secondary" onClick={toggle}>
      <Icon aria-hidden size={ICON_SIZE.md} strokeWidth={ICON_STROKE} />
      {isDark ? '밝게 보기' : '어둡게 보기'}
    </Button>
  );
};

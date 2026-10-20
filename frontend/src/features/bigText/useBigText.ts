import { useContext } from 'react';

import { BigTextContext } from '@/features/bigText/BigTextProvider';

export const useBigText = () => {
  const context = useContext(BigTextContext);
  if (!context) throw new Error('useBigText는 BigTextProvider 안에서만 쓸 수 있어요.');
  return context;
};

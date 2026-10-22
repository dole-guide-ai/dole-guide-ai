'use client';

import { createContext, useCallback, useEffect, useMemo, useState } from 'react';

export interface BigTextContextValue {
  isBig: boolean;
  setIsBig: (isBig: boolean) => void;
  toggle: () => void;
}

export const BigTextContext = createContext<BigTextContextValue | null>(null);

interface BigTextProviderProps {
  children: React.ReactNode;
}

/** `글자 크게` 상태 (1.6 M4). 루트 요소의 data 속성만 바꾸고 크기는 globals.css가 정합니다. */
export const BigTextProvider = ({ children }: BigTextProviderProps) => {
  const [isBig, setIsBig] = useState(false);

  useEffect(() => {
    document.documentElement.dataset.bigText = isBig ? 'true' : 'false';
  }, [isBig]);

  const toggle = useCallback(() => setIsBig((prev) => !prev), []);

  const value = useMemo(() => ({ isBig, setIsBig, toggle }), [isBig, toggle]);

  return <BigTextContext value={value}>{children}</BigTextContext>;
};

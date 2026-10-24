import { useCallback, useSyncExternalStore } from 'react';

import { THEME, type Theme, THEME_STORAGE_KEY } from '@/features/theme/theme';

const listeners = new Set<() => void>();

const readTheme = (): Theme =>
  document.documentElement.dataset.theme === THEME.DARK ? THEME.DARK : THEME.LIGHT;

const subscribe = (listener: () => void) => {
  listeners.add(listener);
  return () => listeners.delete(listener);
};

/** 지금 테마와 바꾸기. 바꾼 값은 브라우저에 기억합니다(다음 방문에도 유지). */
export const useTheme = () => {
  const theme = useSyncExternalStore(subscribe, readTheme, () => THEME.LIGHT);

  const toggle = useCallback(() => {
    const next = readTheme() === THEME.DARK ? THEME.LIGHT : THEME.DARK;
    document.documentElement.dataset.theme = next;
    try {
      window.localStorage.setItem(THEME_STORAGE_KEY, next);
    } catch {
      // 저장이 막혀도 이번 화면에서는 바뀐 테마가 유지됩니다.
    }
    listeners.forEach((listener) => listener());
  }, []);

  return { theme, isDark: theme === THEME.DARK, toggle };
};

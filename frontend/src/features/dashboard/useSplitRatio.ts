import { useCallback, useSyncExternalStore } from 'react';

/** 대화창 폭(%) 범위와 기본값. 기본 45%는 예전 고정 비율(5fr : 6fr)과 같습니다. */
export const SPLIT_RATIO = { min: 30, max: 65, default: 45, step: 5 } as const;

const STORAGE_KEY = 'dole.dashboard.chatWidth';
const listeners = new Set<() => void>();
// 저장이 막힌 브라우저에서도 이번 화면 동안은 값을 유지합니다.
let memoryRatio: number | null = null;

export const clampRatio = (value: number) =>
  Math.min(SPLIT_RATIO.max, Math.max(SPLIT_RATIO.min, Math.round(value)));

const readRatio = (): number => {
  if (memoryRatio !== null) return memoryRatio;
  try {
    const saved = Number(window.localStorage.getItem(STORAGE_KEY));
    return saved > 0 ? clampRatio(saved) : SPLIT_RATIO.default;
  } catch {
    return SPLIT_RATIO.default;
  }
};

const subscribe = (listener: () => void) => {
  listeners.add(listener);
  return () => listeners.delete(listener);
};

/** 대화창·패널 사이 폭 비율. 숫자 하나만 브라우저에 기억합니다(대화 내용은 저장하지 않음). */
export const useSplitRatio = () => {
  const ratio = useSyncExternalStore(subscribe, readRatio, () => SPLIT_RATIO.default);

  const setRatio = useCallback((value: number) => {
    memoryRatio = clampRatio(value);
    try {
      window.localStorage.setItem(STORAGE_KEY, String(memoryRatio));
    } catch {
      // 저장이 막혀도 memoryRatio로 이번 화면에서는 유지됩니다.
    }
    listeners.forEach((listener) => listener());
  }, []);

  return { ratio, setRatio, reset: () => setRatio(SPLIT_RATIO.default) };
};

import { setPath } from '@/lib/objectPath';
import type { SessionRead } from '@/types/demo.types';

/**
 * 로그인 뒤 받은 세션(상태·파생값·진입 결과)을 보관하는 작은 외부 저장소.
 * 새로 고침에도 남도록 sessionStorage에 같이 적고, `계정 바꾸기`에서 비웁니다 (1.4).
 * `form_update`(form: "procedure")로 절차 상태가 바뀌면 `patchSession`으로 갱신합니다.
 */
const STORAGE_KEY = 'dole-guide.session';

let current: SessionRead | null | undefined;
const listeners = new Set<() => void>();

const readStorage = (): SessionRead | null => {
  if (typeof window === 'undefined') return null;
  try {
    const raw = window.sessionStorage.getItem(STORAGE_KEY);
    return raw ? (JSON.parse(raw) as SessionRead) : null;
  } catch {
    return null;
  }
};

const writeStorage = (session: SessionRead | null) => {
  if (typeof window === 'undefined') return;
  try {
    if (session) window.sessionStorage.setItem(STORAGE_KEY, JSON.stringify(session));
    else window.sessionStorage.removeItem(STORAGE_KEY);
  } catch {
    // 시크릿 창 등 저장소를 못 쓰는 환경에서는 메모리에만 둡니다.
  }
};

export const getSession = (): SessionRead | null => {
  if (current === undefined) current = readStorage();
  return current;
};

export const getServerSession = (): SessionRead | null => null;

export const setSession = (session: SessionRead | null) => {
  current = session;
  writeStorage(session);
  listeners.forEach((listener) => listener());
};

/** 세션의 한 값만 바꿉니다. 경로는 `state.next_recognition_date`처럼 세션 객체 기준입니다. */
export const patchSession = (path: string, value: unknown) => {
  const session = getSession();
  if (!session) return;
  setSession(setPath(session, path, value));
};

export const subscribeSession = (listener: () => void) => {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
};

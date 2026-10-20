import { useSyncExternalStore } from 'react';

import { getServerSession, getSession, subscribeSession } from '@/lib/sessionStore';

/** 로그인 뒤 저장된 세션. 서버 렌더링에서는 항상 null입니다. */
export const useSession = () =>
  useSyncExternalStore(subscribeSession, getSession, getServerSession);

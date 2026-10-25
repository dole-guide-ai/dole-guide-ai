'use client';

import { useEffect, useSyncExternalStore } from 'react';
import { useRouter } from 'next/navigation';

import { Spinner } from '@/components/Spinner';
import { DashboardView } from '@/features/dashboard/DashboardView';
import { usePersonaName } from '@/features/session/usePersonaName';
import { useSession } from '@/features/session/useSession';

const noopSubscribe = () => () => {};

/** 서버 렌더링 중에는 false, 브라우저에서 하이드레이션이 끝나면 true. */
const useIsHydrated = () =>
  useSyncExternalStore(
    noopSubscribe,
    () => true,
    () => false,
  );

/** 세션이 없으면 로그인으로 돌려보내고, 있으면 대시보드를 보여 줍니다. */
export const DashboardScreen = () => {
  const router = useRouter();
  const session = useSession();
  const personaName = usePersonaName(session);
  const isHydrated = useIsHydrated();

  useEffect(() => {
    if (isHydrated && !session) router.replace('/');
  }, [isHydrated, session, router]);

  if (!session) {
    return (
      <main className="flex min-h-screen items-center justify-center">
        <Spinner label="화면을 준비하는 중…" />
      </main>
    );
  }

  return <DashboardView session={session} personaName={personaName} />;
};

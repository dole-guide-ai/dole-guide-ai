import { PersonaList } from '@/features/auth/PersonaList';
import { HealthStatus } from '@/features/health/HealthStatus';

import { API_BASE_URL, IS_MOCK_API } from '@/lib/api';

/** 시안 1-1 로그인 화면: 시연 고지(①) → 가상 계정 카드(②). */
export const LoginScreen = () => (
  <main className="mx-auto flex min-h-screen w-full max-w-2xl flex-col gap-8 px-4 py-10">
    <header className="flex flex-col gap-3">
      <p className="text-brand text-base font-semibold">실업급여 길잡이</p>
      <h1 className="text-3xl font-bold">누구로 시작할까요?</h1>
      <p className="border-warn/30 bg-warn-soft text-ink rounded-xl border px-4 py-3 text-base">
        이 서비스는 시연용 모의 서비스예요. 실제 개인정보를 쓰지 않고, 고용24와 연결되어 있지
        않아요. 아래 계정은 모두 가상 인물이에요.
      </p>
    </header>

    <section aria-labelledby="persona-heading" className="flex flex-col gap-3">
      <h2 id="persona-heading" className="text-muted text-lg font-semibold">
        가상 계정을 고르면 그 사람의 상황에 맞춰 안내가 시작돼요
      </h2>
      <PersonaList />
    </section>

    <footer className="text-muted mt-auto flex flex-wrap items-center justify-between gap-2 text-sm">
      <span>개인정보를 입력하지 마세요(데모)</span>
      <span className="flex items-center gap-3">
        {/* 모의 모드인지 실제 서버인지 바로 알 수 있게 표시합니다 (NEXT_PUBLIC_USE_MOCK). */}
        <span>{IS_MOCK_API ? '모의 응답 모드' : `서버 ${API_BASE_URL}`}</span>
        <HealthStatus />
      </span>
    </footer>
  </main>
);

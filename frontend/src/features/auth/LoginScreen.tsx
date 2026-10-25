import Image from 'next/image';

import { PersonaList } from '@/features/auth/PersonaList';

/** 시안 1-1 로그인 화면: 시연 고지(①) → 가상 계정 카드(②). */
export const LoginScreen = () => (
  <main className="mx-auto flex min-h-screen w-full max-w-2xl flex-col gap-8 px-4 py-10">
    <header className="flex flex-col gap-3">
      {/* SVG는 최적화가 필요 없어 그대로 씁니다 (public/brand). */}
      <Image
        src="/brand/logo-stacked.svg"
        alt="실업급여 길잡이"
        width={154}
        height={120}
        priority
        unoptimized
        className="in-data-[theme=dark]:hidden"
      />
      <Image
        src="/brand/logo-stacked-dark.svg"
        alt="실업급여 길잡이"
        width={154}
        height={120}
        priority
        unoptimized
        className="hidden in-data-[theme=dark]:block"
      />
      <h1 className="text-3xl font-bold">누구로 시작할까요?</h1>
      <p className="border-warn bg-warn-soft text-ink rounded-xl border px-4 py-3 text-base">
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

    <footer className="text-muted mt-auto text-sm">개인정보를 입력하지 마세요(데모)</footer>
  </main>
);

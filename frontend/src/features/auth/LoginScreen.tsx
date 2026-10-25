import Image from 'next/image';

import { PersonaList } from '@/features/auth/PersonaList';
import { ServiceIntro } from '@/features/auth/ServiceIntro';

/** 시안 1-1 로그인 화면: 서비스 소개 → 가상 계정 카드(②) → 시연 고지(①, 맨 아래). */
export const LoginScreen = () => (
  <main className="mx-auto flex min-h-screen w-full max-w-6xl flex-col gap-8 px-4 py-10">
    <ServiceIntro
      logo={
        <>
          {/* 세로 로고를 작게 줄여 소개 문구 왼쪽에 둡니다. SVG는 최적화가 필요 없어 그대로 씁니다 (public/brand). */}
          <Image
            src="/brand/logo-stacked.svg"
            alt="실업급여 길잡이"
            width={92}
            height={72}
            priority
            unoptimized
            className="in-data-[theme=dark]:hidden"
          />
          <Image
            src="/brand/logo-stacked-dark.svg"
            alt="실업급여 길잡이"
            width={92}
            height={72}
            priority
            unoptimized
            className="hidden in-data-[theme=dark]:block"
          />
        </>
      }
    />

    <section aria-labelledby="persona-heading" className="flex flex-col gap-3">
      <div className="flex flex-col gap-1">
        <h2 id="persona-heading" className="text-2xl font-bold">
          누구로 시작할까요?
        </h2>
        <p className="text-muted text-base">
          가상 계정을 고르면 그 사람의 상황에 맞춰 안내가 시작돼요.
        </p>
      </div>
      <PersonaList />
    </section>

    {/* 시연 고지(①): 맨 아래에 색 없이 둡니다. */}
    <footer className="border-line text-muted mt-auto flex flex-col gap-1 border-t pt-5 text-sm">
      <p>
        시연용 서비스예요. 대화는 실제 AI 에이전트가 답하지만, 고용24와는 연결되어 있지 않아 실제로
        신청되지는 않아요.
      </p>
      <p>아래 계정은 모두 가상 인물이고, 실제 개인정보는 쓰지 않아요.</p>
    </footer>
  </main>
);

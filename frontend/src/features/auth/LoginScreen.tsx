import Image from 'next/image';

import { PersonaList } from '@/features/auth/PersonaList';
import { ServiceIntro } from '@/features/auth/ServiceIntro';
import { SiteFooter } from '@/features/auth/SiteFooter';

/** 시안 1-1 로그인 화면: 서비스 소개 → 가상 계정 카드(②) → 바닥글(링크·시연 고지①·저작권). */
export const LoginScreen = () => (
  <div className="flex min-h-screen flex-col">
    <main className="mx-auto flex w-full max-w-6xl flex-1 flex-col gap-8 px-4 py-10">
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
    </main>
    <SiteFooter />
  </div>
);

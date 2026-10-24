'use client';

import type { ReactNode } from 'react';
import Image from 'next/image';

import { ArrowLeftRight, UserRound } from 'lucide-react';

import { Button } from '@/components/Button';
import { BigTextToggle } from '@/features/bigText/BigTextToggle';
import { ThemeToggle } from '@/features/theme/ThemeToggle';

import { ICON_SIZE, ICON_STROKE } from '@/lib/iconSize';

/**
 * 대시보드 상단 (1.5 · 시연 개선 4번)
 * - 첫 줄: 로고 | 지금 단계 제목 · 다음 할 일 | 화면 설정(누구 계정인지는 `OOO님 정보 보기` 버튼에 보임). 제목과 다음 할 일은 기준선을 맞춰 한 줄에 두고,
 *   다음 할 일은 남은 폭만큼 보이다 말줄임됩니다(전체 문구는 title).
 * - 둘째 줄: 진행바. 진행바까지 한 줄에 두면 넓은 화면에서도 버튼이 밀려 내려가 따로 얇은 줄로 뺐습니다.
 * 폭이 모자라면(좁은 화면·글자 크게) 영역 단위로 줄바꿈합니다. 아래 1px 선으로 대화 영역과 나눕니다.
 */
interface DashboardHeaderProps {
  personaName: string;
  title: string;
  nextStepText: string;
  progress: ReactNode;
  onSwitchAccount: () => void;
  onOpenMyData?: () => void;
}

export const DashboardHeader = ({
  personaName,
  title,
  nextStepText,
  progress,
  onSwitchAccount,
  onOpenMyData,
}: DashboardHeaderProps) => (
  <header className="bg-surface relative">
    <div className="flex flex-wrap items-center gap-x-6 gap-y-3 px-4 py-3 sm:px-6">
      <div className="flex shrink-0 items-center gap-3">
        {/* 밝게·어둡게 로고를 둘 다 두고 테마에 맞는 것만 보입니다(첫 그림 전에 정해져 깜빡이지 않음). */}
        <Image
          src="/brand/logo.svg"
          alt="실업급여 길잡이"
          width={141}
          height={32}
          priority
          unoptimized
          className="in-data-[theme=dark]:hidden"
        />
        <Image
          src="/brand/logo-dark.svg"
          alt="실업급여 길잡이"
          width={141}
          height={32}
          priority
          unoptimized
          className="hidden in-data-[theme=dark]:block"
        />
      </div>
      <span className="bg-line hidden h-6 w-px sm:block" aria-hidden />
      <div className="flex min-w-60 flex-1 items-baseline gap-3">
        <h1 className="shrink-0 text-lg leading-tight font-bold">{title}</h1>
        <p className="text-muted min-w-0 truncate text-base" title={nextStepText}>
          {nextStepText}
        </p>
      </div>
      <nav className="ml-auto flex shrink-0 flex-wrap items-center gap-2" aria-label="화면 설정">
        <BigTextToggle />
        <ThemeToggle />
        <Button variant="secondary" onClick={onOpenMyData} disabled={!onOpenMyData}>
          <UserRound aria-hidden size={ICON_SIZE.md} strokeWidth={ICON_STROKE} />
          {personaName}님 정보 보기
        </Button>
        <Button variant="ghost" onClick={onSwitchAccount}>
          <ArrowLeftRight aria-hidden size={ICON_SIZE.md} strokeWidth={ICON_STROKE} />
          계정 바꾸기
        </Button>
      </nav>
    </div>
    <div className="border-line border-y px-4 py-2 sm:px-6">{progress}</div>
  </header>
);

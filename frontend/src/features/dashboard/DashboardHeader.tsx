'use client';

import type { ReactNode } from 'react';
import Image from 'next/image';

import { Button } from '@/components/Button';
import { BigTextToggle } from '@/features/bigText/BigTextToggle';

/**
 * 대시보드 상단 한 줄 (1.5 · 시연 개선 4번): 로고·이름 · 지금 단계 제목과 다음 할 일 · 진행바 · 화면 설정.
 * 넓은 화면은 한 줄, 폭이 모자라면(좁은 화면·글자 크게) 줄바꿈합니다. 대화창과 패널이 쓸 세로 공간을 넓히려고 한 영역으로 합쳤습니다.
 * 진행바·버튼은 줄지 않고 제목 영역이 남은 폭을 씁니다. 제목이 너무 좁아지기 전에 줄을 바꾸고, 다음 할 일은 두 줄까지 보입니다.
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
  <header className="border-line bg-surface flex flex-wrap items-center gap-x-6 gap-y-2 border-b px-4 py-2 sm:px-6">
    <div className="border-line flex shrink-0 items-center gap-3 sm:border-r sm:pr-6">
      <Image
        src="/brand/logo.svg"
        alt="실업급여 길잡이"
        width={141}
        height={32}
        priority
        unoptimized
      />
      <span className="bg-neutral-soft text-ink rounded-full px-3 py-1 text-sm font-semibold">
        {personaName}님
      </span>
    </div>
    <div className="flex min-w-60 flex-1 flex-col gap-0.5">
      <h1 className="text-xl leading-tight font-bold">{title}</h1>
      <p className="text-muted line-clamp-2 text-sm">{nextStepText}</p>
    </div>
    <div className="shrink-0">{progress}</div>
    <nav className="ml-auto flex shrink-0 flex-wrap items-center gap-2" aria-label="화면 설정">
      <BigTextToggle />
      <Button variant="secondary" onClick={onOpenMyData} disabled={!onOpenMyData}>
        내 정보
      </Button>
      <Button variant="ghost" onClick={onSwitchAccount}>
        계정 바꾸기
      </Button>
    </nav>
  </header>
);

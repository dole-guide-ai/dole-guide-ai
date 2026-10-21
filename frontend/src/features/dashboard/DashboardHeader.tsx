'use client';

import type { ReactNode } from 'react';
import Image from 'next/image';

import { Button } from '@/components/Button';
import { BigTextToggle } from '@/features/bigText/BigTextToggle';

/**
 * 대시보드 상단 한 줄 (1.5 · 시연 개선 4번): 로고·이름 · 지금 단계 제목과 다음 할 일 · 진행바 · 화면 설정.
 * 넓은 화면은 한 줄, 좁은 화면은 줄바꿈합니다. 대화창과 패널이 쓸 세로 공간을 넓히려고 한 영역으로 합쳤습니다.
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
    <div className="flex items-center gap-3">
      <Image
        src="/brand/logo.svg"
        alt="실업급여 길잡이"
        width={141}
        height={32}
        priority
        unoptimized
      />
      <span className="text-muted text-base">{personaName}님</span>
    </div>
    <div className="min-w-0">
      <h1 className="text-xl leading-tight font-bold">{title}</h1>
      <p className="text-muted text-sm">{nextStepText}</p>
    </div>
    {progress}
    <nav className="ml-auto flex flex-wrap items-center gap-2" aria-label="화면 설정">
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

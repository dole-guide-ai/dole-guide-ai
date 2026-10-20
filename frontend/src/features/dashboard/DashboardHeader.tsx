'use client';

import Image from 'next/image';

import { Button } from '@/components/Button';
import { BigTextToggle } from '@/features/bigText/BigTextToggle';

interface DashboardHeaderProps {
  personaName: string;
  onSwitchAccount: () => void;
  onOpenMyData?: () => void;
}

export const DashboardHeader = ({
  personaName,
  onSwitchAccount,
  onOpenMyData,
}: DashboardHeaderProps) => (
  <header className="border-line bg-surface flex flex-wrap items-center justify-between gap-3 border-b px-4 py-3 sm:px-6">
    <div className="flex items-baseline gap-3">
      <Image
        src="/brand/logo.svg"
        alt="실업급여 길잡이"
        width={141}
        height={32}
        priority
        unoptimized
        className="self-center"
      />
      <span className="text-muted text-base">{personaName}님</span>
    </div>
    <nav className="flex flex-wrap items-center gap-2" aria-label="화면 설정">
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

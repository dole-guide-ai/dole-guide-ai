'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';

import { ProgressBar } from '@/components/ProgressBar';
import { useBigText } from '@/features/bigText/useBigText';
import { ChatPanel } from '@/features/chat/ChatPanel';
import { useChatMessages } from '@/features/chat/useChatMessages';
import { DashboardHeader } from '@/features/dashboard/DashboardHeader';
import { PanelFrame } from '@/features/dashboard/PanelFrame';

import { setSession } from '@/lib/sessionStore';
import type { SessionRead } from '@/types/demo.types';

interface DashboardViewProps {
  session: SessionRead;
  personaName: string;
}

/** 대시보드 본문 (1.5): 진행바 · 다음 할 일 · 대화 · 패널. */
export const DashboardView = ({ session, personaName }: DashboardViewProps) => {
  const router = useRouter();
  const { setIsBig } = useBigText();
  const { messages, choices, sendUserMessage } = useChatMessages(session);
  const { entry } = session;
  const bigTextDefault = entry.ui.big_text;

  // M4: 65세 이상 계정은 처음부터 글자 크게. 세션이 바뀔 때만 기본값을 다시 적용합니다.
  useEffect(() => {
    setIsBig(bigTextDefault);
  }, [session.session_id, bigTextDefault, setIsBig]);

  const handleSwitchAccount = () => {
    setSession(null);
    router.push('/');
  };

  return (
    <div className="flex min-h-screen flex-col">
      <DashboardHeader personaName={personaName} onSwitchAccount={handleSwitchAccount} />

      <section className="border-line bg-surface flex flex-col gap-3 border-b px-4 py-4 sm:px-6">
        <ProgressBar current={entry.progress.current} done={entry.progress.done} />
        <div>
          <h1 className="text-2xl font-bold">{entry.title}</h1>
          <p className="text-muted text-base">{entry.next_step_text}</p>
        </div>
      </section>

      <main className="grid flex-1 gap-4 p-4 sm:p-6 lg:grid-cols-[minmax(0,5fr)_minmax(0,6fr)]">
        <ChatPanel
          messages={messages}
          choices={choices}
          onChoice={(choice) => sendUserMessage(choice, 'choice')}
          onSend={(text) => sendUserMessage(text)}
          isInputDisabled
          inputDisabledReason="대화 입력은 다음 단계에서 열려요"
        />
        <PanelFrame session={session} />
      </main>
    </div>
  );
};

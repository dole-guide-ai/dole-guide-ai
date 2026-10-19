'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';

import { ProgressBar } from '@/components/ProgressBar';
import { useBigText } from '@/features/bigText/useBigText';
import { ChatPanel } from '@/features/chat/ChatPanel';
import { useChatStream } from '@/features/chat/useChatStream';
import { DashboardHeader } from '@/features/dashboard/DashboardHeader';
import { PanelFrame } from '@/features/dashboard/PanelFrame';

import { resetForms } from '@/lib/formStore';
import { setSession } from '@/lib/sessionStore';
import type { SessionRead } from '@/types/demo.types';

interface DashboardViewProps {
  session: SessionRead;
  personaName: string;
}

/** 도구 이름을 사람이 읽을 상태 문구로 바꿉니다 (`tool_call` 이벤트). */
const TOOL_LABEL: Record<string, string> = {
  check_activity_rules: '회차 규칙을 점검하는 중…',
  parse_file: '서류를 읽는 중…',
  lookup_code: '직종·지역 코드를 찾는 중…',
  search_guide: '근거 자료를 찾는 중…',
};

/** 대시보드 본문 (1.5): 진행바 · 다음 할 일 · 대화 · 패널. */
export const DashboardView = ({ session, personaName }: DashboardViewProps) => {
  const router = useRouter();
  const { setIsBig } = useBigText();
  const chat = useChatStream(session);
  const { entry } = session;
  const bigTextDefault = entry.ui.big_text;

  // M4: 65세 이상 계정은 처음부터 글자 크게. 세션이 바뀔 때만 기본값을 다시 적용합니다.
  useEffect(() => {
    setIsBig(bigTextDefault);
  }, [session.session_id, bigTextDefault, setIsBig]);

  const handleSwitchAccount = () => {
    resetForms();
    setSession(null);
    router.push('/');
  };

  const statusText = chat.activeTool
    ? (TOOL_LABEL[chat.activeTool] ?? '처리하는 중…')
    : chat.isStreaming
      ? '답을 만드는 중…'
      : null;

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
          messages={chat.messages}
          choices={chat.choices}
          inputText={chat.inputText}
          onInputChange={chat.setInputText}
          onChoice={(choice) => chat.send(choice, 'choice')}
          onSend={(text) => chat.send(text)}
          isStreaming={chat.isStreaming}
          statusText={statusText}
        />
        <PanelFrame
          session={session}
          onEditRequest={(label) => chat.setInputText(`${label} 고칠게요`)}
        />
      </main>
    </div>
  );
};

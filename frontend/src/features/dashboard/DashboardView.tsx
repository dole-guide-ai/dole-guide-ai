'use client';

import { type CSSProperties, useEffect, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';

import { ProgressBar } from '@/components/ProgressBar';
import { useBigText } from '@/features/bigText/useBigText';
import { ChatPanel } from '@/features/chat/ChatPanel';
import { useChatStream } from '@/features/chat/useChatStream';
import { useFileUpload } from '@/features/chat/useFileUpload';
import { DashboardHeader } from '@/features/dashboard/DashboardHeader';
import { NoticeToast } from '@/features/dashboard/NoticeToast';
import { PanelFrame } from '@/features/dashboard/PanelFrame';
import { sessionNotices } from '@/features/dashboard/sessionNotices';
import { SplitHandle } from '@/features/dashboard/SplitHandle';
import { useSplitRatio } from '@/features/dashboard/useSplitRatio';
import { MyDataDialog } from '@/features/myData/MyDataDialog';
import { CONFIRMED_MESSAGE } from '@/features/recognition/recognitionLabels';

import { ApiError } from '@/lib/api';
import { resetForms } from '@/lib/formStore';
import { setSession } from '@/lib/sessionStore';
import type { ProgressStep, SessionRead } from '@/types/demo.types';

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

/** 대시보드 본문 (1.5): 상단 한 줄(진행바 · 다음 할 일) · 대화 · 패널. */
export const DashboardView = ({ session, personaName }: DashboardViewProps) => {
  const router = useRouter();
  const { setIsBig } = useBigText();
  const chat = useChatStream(session);
  // 진행바에서 고른 완료 단계 (1.8 읽기 전용 다시 보기). 세션이 바뀌면 지금 단계로 돌아옵니다.
  const [review, setReview] = useState<{ sessionId: string; step: ProgressStep } | null>(null);
  const reviewStep = review?.sessionId === session.session_id ? review.step : null;
  const [isMyDataOpen, setIsMyDataOpen] = useState(false);
  const split = useSplitRatio();
  const mainRef = useRef<HTMLElement>(null);
  const upload = useFileUpload(session.persona_id, session.state.stage);
  const { entry } = session;
  const bigTextDefault = entry.ui.big_text;

  // M4: 65세 이상 계정은 처음부터 글자 크게. 세션이 바뀔 때만 기본값을 다시 적용합니다.
  useEffect(() => {
    setIsBig(bigTextDefault);
  }, [session.session_id, bigTextDefault, setIsBig]);

  // F-22: 대화 응답을 기다리지 않고 바로 신청서(패널 C)를 엽니다.
  const handleOpenForm = () => setSession({ ...session, entry: { ...entry, panel: 'C' } });

  const handleSwitchAccount = () => {
    resetForms();
    setSession(null);
    router.push('/');
  };

  /** 파일을 올린 뒤 `file_ids`를 붙여 대화로 보냅니다. 판독 결과는 스트림(`tool_call` parse_file)으로 옵니다. */
  const handleFileSelect = (file: File) => {
    upload.mutate(file, {
      onSuccess: ({ file_id }) =>
        void chat.send('파일을 올렸어요. 읽어 주세요.', {
          fileIds: [file_id],
          attachments: [{ name: file.name }],
        }),
      onError: (error) =>
        chat.notifySystem(
          error instanceof ApiError ? error.message : '파일을 올리지 못했어요. 다시 시도해 주세요.',
        ),
    });
  };

  const statusText = chat.activeTool
    ? (TOOL_LABEL[chat.activeTool] ?? '처리하는 중…')
    : chat.isStreaming
      ? '답을 만드는 중…'
      : upload.isPending
        ? '파일을 올리는 중…'
        : null;

  return (
    // 넓은 화면은 화면 높이에 고정하고 대화·패널이 각자 스크롤됩니다. 좁은 화면(세로로 쌓임)은 페이지가 스크롤됩니다.
    <div className="flex min-h-dvh flex-col lg:h-dvh lg:overflow-hidden">
      <DashboardHeader
        personaName={personaName}
        title={entry.title}
        nextStepText={entry.next_step_text}
        progress={
          <ProgressBar
            current={entry.progress.current}
            done={entry.progress.done}
            onStepClick={(step) => setReview({ sessionId: session.session_id, step })}
            isCompact
          />
        }
        onSwitchAccount={handleSwitchAccount}
        onOpenMyData={() => setIsMyDataOpen(true)}
      />
      <NoticeToast key={session.session_id} notices={sessionNotices(session)} />
      {isMyDataOpen && (
        <MyDataDialog personaId={session.persona_id} onClose={() => setIsMyDataOpen(false)} />
      )}

      {/* 넓은 화면: 대화창 | 손잡이 | 패널. 대화창 폭은 손잡이로 바꾸는 --chat-width(%)입니다. */}
      <main
        ref={mainRef}
        style={{ '--chat-width': `${split.ratio}%` } as CSSProperties}
        className="grid flex-1 gap-4 p-4 sm:px-6 sm:pt-6 lg:min-h-0 lg:grid-cols-[minmax(0,var(--chat-width))_auto_minmax(0,1fr)] lg:gap-2"
      >
        <ChatPanel
          messages={chat.messages}
          choices={chat.choices}
          importKind={chat.importKind}
          sessionId={session.session_id}
          personaId={session.persona_id}
          onImport={(importIds) =>
            void chat.send(`고용24에서 고른 ${importIds.length}건 넣어 주세요`, {
              inputKind: 'choice',
              importIds,
            })
          }
          inputText={chat.inputText}
          onInputChange={chat.setInputText}
          onChoice={(choice) => chat.send(choice, { inputKind: 'choice' })}
          onSend={(text) => chat.send(text)}
          onFileSelect={handleFileSelect}
          isFileRequested={chat.acceptsFile}
          isStreaming={chat.isStreaming}
          isUploading={upload.isPending}
          statusText={statusText}
        />
        <SplitHandle
          ratio={split.ratio}
          onChange={split.setRatio}
          onReset={split.reset}
          containerRef={mainRef}
          controlsId="dashboard-chat"
        />
        <PanelFrame
          session={session}
          onEditRequest={(label) => chat.setInputText(`${label} 고칠게요`)}
          onOpenForm={handleOpenForm}
          reviewStep={reviewStep}
          onExitReview={() => setReview(null)}
          onFormConfirmed={(mode) =>
            void chat.send(CONFIRMED_MESSAGE[mode], { inputKind: 'choice' })
          }
        />
      </main>
    </div>
  );
};

import { useState } from 'react';

import {
  ClipboardCheck,
  FilePen,
  FileText,
  ListChecks,
  type LucideIcon,
  MonitorPlay,
} from 'lucide-react';

import { Button } from '@/components/Button';
import { EvidenceLine } from '@/components/EvidenceLine';
import { showsVisitNotice } from '@/features/dashboard/sessionNotices';
import { BenefitEndedPanel } from '@/features/procedure/BenefitEndedPanel';
import { RoundPanel } from '@/features/procedure/RoundPanel';
import { RecognitionPanel } from '@/features/recognition/RecognitionPanel';
import { ResumePanel } from '@/features/resume/ResumePanel';
import { EducationPanel } from '@/features/steps/EducationPanel';
import { EligibilityPanel } from '@/features/steps/EligibilityPanel';
import { FirstDatePanel } from '@/features/steps/FirstDatePanel';

import { ICON_SIZE, ICON_STROKE } from '@/lib/iconSize';
import { patchSession } from '@/lib/sessionStore';
import { citeOf } from '@/lib/sources';
import type { PanelId, ProgressStep, SessionRead } from '@/types/demo.types';

/**
 * 오른쪽 패널 틀 (1.1 패널 A/E/Q/B/C): A 이력서(2-1), B 회차 할 일(2-2), C 신청서(2-3),
 * E 온라인 교육·Q 수급자격 신청·E5b 1차 인정일 입력(기획 "예정", 정적 화면).
 */
const PANEL_INFO: Record<PanelId, { name: string; description: string; icon: LucideIcon }> = {
  A: {
    name: '이력서',
    icon: FileText,
    description: '고용24 이력서 항목을 같은 순서로 채워요.',
  },
  E: {
    name: '온라인 교육',
    icon: MonitorPlay,
    description: '수급자격 신청자 온라인 교육(약 1시간) 이수를 확인해요.',
  },
  Q: { name: '수급자격 신청', icon: ClipboardCheck, description: '준비물과 신청 경로를 정리해요.' },
  B: {
    name: '이번 회차 할 일',
    icon: ListChecks,
    description: '재취업활동을 기록하고 회차 규칙으로 점검해요.',
  },
  C: {
    name: '실업인정 신청서 검토',
    icon: FilePen,
    description: '정리한 활동으로 신청서를 검토하고 본인이 제출해요.',
  },
};

const SOURCE_WORK24 = citeOf('SRC-001');

interface PanelFrameProps {
  session: SessionRead;
  /** 패널의 `고치기`를 누르면 "{항목} 고칠게요"를 입력창에 넣습니다 (2-0.6). */
  onEditRequest?: (label: string) => void;
  /** 패널 B `활동 정리 끝 · 신청서 만들기` (2-2.9) */
  onOpenForm?: () => void;
  /** 패널 C 모의 제출·출석 준비 확인이 끝났을 때 (2-3.7) */
  onFormConfirmed?: (mode: 'send' | 'attend') => void;
  /** 진행바에서 고른 완료 단계 (1.8): 그 단계 패널을 읽기 전용으로 보여 줍니다. */
  reviewStep?: ProgressStep | null;
  onExitReview?: () => void;
}

/** 완료 단계 → 그 단계의 패널. 4단계(실업인정)는 늘 현재 단계라 다시 보기가 없습니다. */
const STEP_PANEL: Partial<Record<ProgressStep, PanelId>> = { 1: 'A', 2: 'E', 3: 'Q' };

// 박스 없이 화면 오른쪽을 꽉 채우는 영역. 대화와는 왼쪽 손잡이(세로선)로 나뉘고, 스크롤은 안쪽 칸이 맡습니다.
const ASIDE_CLASS = 'bg-surface flex flex-col lg:min-h-0';
const SCROLL_CLASS =
  'scrollbar-hidden flex flex-col gap-6 px-6 py-6 lg:min-h-0 lg:flex-1 lg:overflow-y-auto lg:px-8';

export const PanelFrame = ({
  session,
  onEditRequest,
  onOpenForm,
  onFormConfirmed,
  reviewStep,
  onExitReview,
}: PanelFrameProps) => {
  const { entry, state } = session;
  const panel = entry.panel;
  const reviewPanel = reviewStep ? STEP_PANEL[reviewStep] : undefined;
  const [isEditingResume, setIsEditingResume] = useState(false);
  // 수급이 끝나면(F-33) 고치던 중이었어도 읽기 전용으로 돌립니다.
  const isEnded = state.stage === 'ended';
  const isResumeEditable = isEditingResume && !isEnded;

  if (reviewPanel) {
    const info = PANEL_INFO[reviewPanel];
    return (
      <aside className={ASIDE_CLASS} aria-label={`${info.name} (읽기 전용)`}>
        <div className={SCROLL_CLASS}>
          <div className="bg-ok-soft flex flex-wrap items-center justify-between gap-2 rounded-xl px-4 py-3">
            <p className="text-ok text-base font-semibold">
              완료한 단계 · {info.name} {isResumeEditable ? '(고치는 중)' : '(읽기 전용)'}
            </p>
            <div className="flex flex-wrap gap-2">
              {/* 수급이 끝난 계정은 지난 단계도 읽기만 합니다 (F-33). */}
              {reviewPanel === 'A' && !isEditingResume && !isEnded && (
                <Button variant="secondary" onClick={() => setIsEditingResume(true)}>
                  이력서 고치기
                </Button>
              )}
              {onExitReview && (
                <Button
                  variant="secondary"
                  onClick={() => {
                    setIsEditingResume(false);
                    onExitReview();
                  }}
                >
                  이번 단계로 돌아가기
                </Button>
              )}
            </div>
          </div>
          {reviewPanel === 'A' && (
            <ResumePanel
              session={session}
              isReadOnly={!isResumeEditable}
              onEditRequest={onEditRequest}
              saveLabel="다시 저장하기"
              onSaved={() => setIsEditingResume(false)}
            />
          )}
          {reviewPanel === 'E' && <EducationPanel state={state} isReadOnly />}
          {reviewPanel === 'Q' && (
            <EligibilityPanel state={state} derived={session.derived} isReadOnly />
          )}
        </div>
      </aside>
    );
  }

  if (!panel) {
    return (
      <aside className={ASIDE_CLASS} aria-label="패널">
        <p className="text-muted p-5 text-base">
          지금 단계를 알려 주시면 맞는 화면을 보여 드릴게요.
        </p>
      </aside>
    );
  }

  const info = PANEL_INFO[panel];

  return (
    <aside className={ASIDE_CLASS} aria-label={info.name}>
      <div className={SCROLL_CLASS}>
        <div className="flex items-start gap-3">
          <span
            aria-hidden
            className="bg-neutral-soft text-ink flex size-11 shrink-0 items-center justify-center rounded-xl"
          >
            <info.icon size={ICON_SIZE.lg} strokeWidth={ICON_STROKE} />
          </span>
          <div className="flex flex-col gap-0.5">
            <h2 className="text-xl leading-tight font-bold">{info.name}</h2>
            <p className="text-muted text-base">{info.description}</p>
          </div>
        </div>

        {showsVisitNotice(state) && (
          <div className="border-warn/30 bg-warn-soft flex flex-col gap-2 rounded-xl border px-4 py-3">
            <p className="text-warn text-base font-semibold">신청 경로 안내</p>
            <p className="text-base">
              이직일 기준 만 65세 이상이라 수급자격 신청은 관할 고용센터에 방문해서 해요. 인터넷
              사전제출은 이직일 기준 만 65세 미만일 때만 할 수 있어요.
            </p>
            <EvidenceLine cite={SOURCE_WORK24} />
          </div>
        )}

        {panel === 'A' && <ResumePanel session={session} onEditRequest={onEditRequest} />}

        {panel === 'B' && isEnded && <BenefitEndedPanel derived={session.derived} />}

        {panel === 'B' &&
          !isEnded &&
          (state.stage === 'eligibility_applied' || !state.next_recognition_date ? (
            // E5b · 1.10 예외: 인정일을 모르면 회차 점검 대신 1차 실업인정일을 먼저 받습니다.
            <FirstDatePanel state={state} />
          ) : (
            <RoundPanel session={session} onOpenForm={onOpenForm} />
          ))}

        {panel === 'C' && (
          <RecognitionPanel
            session={session}
            // 패널을 바꾸는 화면 이동이라 서버를 거치지 않고 세션의 시작 패널만 바꿉니다.
            onBackToRound={() => patchSession('entry.panel', 'B')}
            onConfirmed={onFormConfirmed}
          />
        )}

        {panel === 'E' && <EducationPanel state={state} />}

        {panel === 'Q' && <EligibilityPanel state={state} derived={session.derived} />}
      </div>
    </aside>
  );
};

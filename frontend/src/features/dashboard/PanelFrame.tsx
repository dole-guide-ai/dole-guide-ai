import { EvidenceLine } from '@/components/EvidenceLine';
import { RoundPanel } from '@/features/procedure/RoundPanel';
import { ResumePanel } from '@/features/resume/ResumePanel';

import type { PanelId, SessionRead } from '@/types/demo.types';

/**
 * 오른쪽 패널 틀 (1.1 패널 A/E/Q/B/C). 패널 A는 이력서(2-1), 나머지 양식 칸(활동 목록·신청서)은
 * 2-2 · 2-3 구현에서 채웁니다.
 */
const PANEL_INFO: Record<PanelId, { name: string; description: string }> = {
  A: { name: '이력서', description: '고용24 이력서 항목을 같은 순서로 채워요.' },
  E: { name: '온라인 교육', description: '수급자격 신청자 온라인 교육(약 1시간) 이수를 확인해요.' },
  Q: { name: '수급자격 신청', description: '준비물과 신청 경로를 정리해요.' },
  B: { name: '이번 회차 할 일', description: '재취업활동을 기록하고 회차 규칙으로 점검해요.' },
  C: {
    name: '실업인정 신청서 검토',
    description: '정리한 활동으로 신청서를 검토하고 본인이 제출해요.',
  },
};

const SOURCE_WORK24 = '고용24 실업급여(상용직)';

interface PanelFrameProps {
  session: SessionRead;
  /** 패널의 `고치기`를 누르면 "{항목} 고칠게요"를 입력창에 넣습니다 (2-0.6). */
  onEditRequest?: (label: string) => void;
  /** 패널 B `활동 정리 끝 · 신청서 만들기` (2-2.9) */
  onOpenForm?: () => void;
}

export const PanelFrame = ({ session, onEditRequest, onOpenForm }: PanelFrameProps) => {
  const { entry, state } = session;
  const panel = entry.panel;

  if (!panel) {
    return (
      <aside className="border-line bg-surface rounded-2xl border p-5" aria-label="패널">
        <p className="text-muted text-base">지금 단계를 알려 주시면 맞는 화면을 보여 드릴게요.</p>
      </aside>
    );
  }

  const info = PANEL_INFO[panel];
  // M1 (1.6): 이직 당시 65세 이상이고 수급자격 신청 전 단계면 신청 경로 안내 상자를 둡니다.
  const showsVisitNotice =
    state.age_at_separation >= 65 &&
    ['job_registration', 'education', 'eligibility_application'].includes(state.stage);

  return (
    <aside
      className="border-line bg-surface flex flex-col gap-4 rounded-2xl border p-5"
      aria-label={`패널 ${info.name}`}
    >
      <div>
        <p className="text-brand text-sm font-semibold">패널 {panel}</p>
        <h2 className="text-xl font-bold">{info.name}</h2>
        <p className="text-muted text-base">{info.description}</p>
      </div>

      {showsVisitNotice && (
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

      {panel === 'B' && <RoundPanel session={session} onOpenForm={onOpenForm} />}

      {panel !== 'A' && panel !== 'B' && (
        <p className="text-muted text-sm">
          양식 칸은 대화를 이어가며 채워져요. 최종 인정 여부는 관할 고용센터가 판단해요.
        </p>
      )}
    </aside>
  );
};

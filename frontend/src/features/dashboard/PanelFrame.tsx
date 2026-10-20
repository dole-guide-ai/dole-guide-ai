import { EvidenceLine } from '@/components/EvidenceLine';
import { DdayCard } from '@/features/procedure/DdayCard';

import type { PanelId, SessionRead } from '@/types/demo.types';

/**
 * 오른쪽 패널 틀 (1.1 패널 A/E/Q/B/C). 이 단계에서는 패널 제목과 상태 요약만 보여 주고,
 * 양식 칸(이력서·활동 목록·신청서)은 2-1 · 2-2 · 2-3 구현에서 채웁니다.
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

const RESUME_STATUS_TEXT: Record<SessionRead['state']['resume_status'], string> = {
  none: '아직 이력서가 없어요. 대화로 함께 만들어요.',
  outdated: '예전 이력서를 불러왔어요. 그 뒤로 바뀐 부분만 더해요.',
  draft: '작성 중인 이력서가 있어요.',
  ready: '이력서가 준비돼 있어요.',
};

const SOURCE_WORK24 = '고용24 실업급여(상용직)';

interface PanelFrameProps {
  session: SessionRead;
}

export const PanelFrame = ({ session }: PanelFrameProps) => {
  const { entry, state, derived } = session;
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

      {panel === 'A' && (
        <p className="bg-canvas rounded-xl px-4 py-3 text-base">
          {RESUME_STATUS_TEXT[state.resume_status]}
        </p>
      )}

      {panel === 'B' && <DdayCard state={state} derived={derived} />}

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

      <p className="text-muted text-sm">
        양식 칸은 대화를 이어가며 채워져요. 최종 인정 여부는 관할 고용센터가 판단해요.
      </p>
    </aside>
  );
};

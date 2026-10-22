import { screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { PanelFrame } from '@/features/dashboard/PanelFrame';

import type { SessionRead } from '@/types/demo.types';
import { buildMockSession } from '@/mocks/handlers';
import { renderWithProviders } from '@/test/renderWithProviders';

const withPanel = (
  personaId: string,
  panel: SessionRead['entry']['panel'],
  state: Partial<SessionRead['state']> = {},
  derived: Partial<SessionRead['derived']> = {},
): SessionRead => {
  const session = buildMockSession(personaId);
  return {
    ...session,
    state: { ...session.state, ...state },
    derived: { ...session.derived, ...derived },
    entry: { ...session.entry, panel },
  };
};

describe('패널 E · Q · E5b (정적)', () => {
  it('E 온라인 교육: 이수 전이면 확인 필요와 대화 안내, 다음 할 일', () => {
    renderWithProviders(
      <PanelFrame
        session={withPanel('park', 'E', { stage: 'education', resume_status: 'ready' })}
      />,
    );

    expect(screen.getByText('아직 이수 전')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '교육을 다 들었어요' })).toBeInTheDocument();
    expect(screen.getByText(/인터넷 사전제출 또는 센터 방문/)).toBeInTheDocument();
  });

  it('Q 수급자격 신청: 65세 이상은 방문 신청과 65세 이후 고용 확인 안내', () => {
    renderWithProviders(
      <PanelFrame
        session={withPanel(
          'choi',
          'Q',
          { stage: 'eligibility_application' },
          { can_presubmit_online: false },
        )}
      />,
    );

    expect(screen.getByText('관할 고용센터에 방문해서 신청')).toBeInTheDocument();
    expect(screen.getByText(/65세 이후에 새로 고용됐거나/)).toBeInTheDocument();
    expect(screen.getByText('신분증')).toBeInTheDocument();
  });

  it('Q 수급자격 신청: 65세 미만은 인터넷 사전제출 조건 4개와 수급기간 12개월을 안내한다', () => {
    renderWithProviders(
      <PanelFrame
        session={withPanel(
          'park',
          'Q',
          { stage: 'eligibility_application' },
          { can_presubmit_online: true },
        )}
      />,
    );

    const conditions = screen.getByRole('region', { name: '인터넷 사전제출 조건' });
    expect(conditions.querySelectorAll('li')).toHaveLength(4);
    expect(screen.getByText(/180일 이상/)).toBeInTheDocument();
    expect(screen.getByText(/그다음 고용센터에 한 번 가야 해요/)).toBeInTheDocument();
    expect(screen.getByText(/12개월 안에서만 받을 수 있어요/)).toBeInTheDocument();
  });

  it('E5b: 신청을 마친 단계의 패널 B는 1차 실업인정일 입력을 요청한다', () => {
    renderWithProviders(
      <PanelFrame
        session={withPanel('lee', 'B', {
          stage: 'eligibility_applied',
          next_recognition_date: null,
        })}
      />,
    );

    expect(screen.getByText('1차 실업인정일을 알려 주세요')).toBeInTheDocument();
    expect(screen.getByText('9.15(화)')).toBeInTheDocument();
    expect(screen.getByText(/7일은 대기기간이라/)).toBeInTheDocument();
    expect(screen.queryByLabelText('필요 활동 결과')).not.toBeInTheDocument();
  });
});

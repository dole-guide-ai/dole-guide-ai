import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { BenefitEndedPanel } from '@/features/procedure/BenefitEndedPanel';
import { BenefitEndNote } from '@/features/procedure/BenefitEndNote';

import { buildMockSession } from '@/mocks/handlers';

describe('수급 종료 예정 (F-33)', () => {
  it('종료 예정일과 이번 회차를 포함한 남은 회차를 보여 준다', () => {
    render(<BenefitEndNote derived={buildMockSession('lee').derived} />);

    expect(screen.getByText(/2027년 6월 11일\(금\)/)).toBeInTheDocument();
    expect(screen.getByText(/남은 회차 8회\(이번 회차 포함\)/)).toBeInTheDocument();
    expect(screen.queryByText(/이번이 마지막 회차예요/)).not.toBeInTheDocument();
  });

  it('마지막 회차면 마지막 회차 문장을 붙인다', () => {
    const { derived } = buildMockSession('lee');
    render(<BenefitEndNote derived={{ ...derived, current_round: 11, remaining_rounds: 1 }} />);

    expect(screen.getByText(/이번이 마지막 회차예요/)).toBeInTheDocument();
  });

  it('종료 예정일이 없으면(회차 전) 아무것도 그리지 않는다', () => {
    const { container } = render(
      <BenefitEndNote derived={{ ...buildMockSession('lee').derived, expected_end_date: null }} />,
    );

    expect(container).toBeEmptyDOMElement();
  });

  it('종료 화면은 종료일과 사유를 보여 준다', () => {
    const { derived } = buildMockSession('lee');
    render(<BenefitEndedPanel derived={{ ...derived, end_reason: 'exhausted' }} />);

    expect(screen.getByText('실업급여 수급이 끝났어요')).toBeInTheDocument();
    expect(screen.getByText(/종료일 2027년 6월 11일/)).toBeInTheDocument();
    expect(screen.getByText('소정급여일수를 모두 받았어요.')).toBeInTheDocument();
  });
});

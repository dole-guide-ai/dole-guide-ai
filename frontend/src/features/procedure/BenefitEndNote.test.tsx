import { screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { BenefitEndedPanel } from '@/features/procedure/BenefitEndedPanel';
import { BenefitEndNote } from '@/features/procedure/BenefitEndNote';

import { buildMockSession } from '@/mocks/handlers';
import { renderWithProviders } from '@/test/renderWithProviders';

// 이정호(270일, 신청일 9.15) 기준 값. 대기기간 다음 날(9.22) + 269일
const LEE_DERIVED = {
  ...buildMockSession('lee').derived,
  expected_end_date: '2027-06-18',
  remaining_rounds: 8,
  last_round: 11,
  end_reason: null,
};

describe('수급 종료 예정 (F-33)', () => {
  it('종료 예정일과 이번 회차를 포함한 남은 회차를 보여 준다', () => {
    renderWithProviders(<BenefitEndNote derived={LEE_DERIVED} />);

    expect(screen.getByText(/2027년 6월 18일\(금\)/)).toBeInTheDocument();
    expect(screen.getByText(/남은 회차 8회\(이번 회차 포함\)/)).toBeInTheDocument();
    expect(screen.queryByText(/이번이 마지막 회차예요/)).not.toBeInTheDocument();
  });

  it('마지막 회차면 마지막 회차 문장을 붙인다', () => {
    const derived = LEE_DERIVED;
    renderWithProviders(
      <BenefitEndNote derived={{ ...derived, current_round: 11, remaining_rounds: 1 }} />,
    );

    expect(screen.getByText(/이번이 마지막 회차예요/)).toBeInTheDocument();
  });

  it('종료 예정일이 없으면(회차 전) 아무것도 그리지 않는다', () => {
    const { container } = renderWithProviders(
      <BenefitEndNote derived={{ ...LEE_DERIVED, expected_end_date: null }} />,
    );

    expect(container).toBeEmptyDOMElement();
  });

  it('종료 화면은 종료일과 사유를 보여 준다', () => {
    const derived = LEE_DERIVED;
    renderWithProviders(<BenefitEndedPanel derived={{ ...derived, end_reason: 'exhausted' }} />);

    expect(screen.getByText('실업급여 수급이 끝났어요')).toBeInTheDocument();
    expect(screen.getByText(/종료일 2027년 6월 18일/)).toBeInTheDocument();
    expect(screen.getByText('소정급여일수를 모두 받았어요.')).toBeInTheDocument();
  });
});

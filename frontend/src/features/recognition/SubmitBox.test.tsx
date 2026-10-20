import { screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { SubmitBox } from '@/features/recognition/SubmitBox';

import type { SubmitMode } from '@/types/recognition.types';
import { renderWithProviders } from '@/test/renderWithProviders';

const renderBox = (mode: SubmitMode, isDone: boolean) =>
  renderWithProviders(
    <SubmitBox
      mode={mode}
      recognitionDate="2026-12-22"
      checklist={[]}
      attendItems={[]}
      canSubmit
      isSubmitting={false}
      isDone={isDone}
      onSubmit={vi.fn()}
    />,
  );

describe('SubmitBox', () => {
  it('인터넷 제출을 마치면 민원처리현황 확인과 다시 전송 안내를 보여 준다 (PROC-080·081)', () => {
    renderBox('send', true);

    expect(screen.getByText(/민원처리현황에서 신청 완료가 됐는지/)).toBeInTheDocument();
    expect(screen.getByText(/반드시 다시 전송해야 해요/)).toBeInTheDocument();
  });

  it('제출 전이나 출석 회차에는 제출 뒤 안내가 없다', () => {
    renderBox('send', false);
    expect(screen.queryByText(/민원처리현황/)).not.toBeInTheDocument();
  });

  it('출석 준비 확인을 마쳐도 인터넷 제출 안내는 나오지 않는다', () => {
    renderBox('attend', true);
    expect(screen.queryByText(/민원처리현황/)).not.toBeInTheDocument();
  });
});

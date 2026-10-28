import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import { FieldRow } from '@/features/resume/FieldRow';

import { ApiError } from '@/lib/api';

describe('FieldRow', () => {
  it('값·칩·근거 보기를 그리고 고치기는 콜백을 부른다', async () => {
    const onEdit = vi.fn();
    render(
      <dl>
        <FieldRow
          label="주요 직무"
          value="프레스 라인 운영"
          meta={{
            status: 'extracted',
            source: 'user_answer',
            transformed: true,
            evidence: {
              kind: 'utterance',
              date: '2026-10-12',
              quote: '작년 3월부터',
              note: "'작년 3월' → 2025-03",
            },
          }}
          onEdit={onEdit}
        />
      </dl>,
    );

    expect(screen.getByText('확인 필요')).toBeInTheDocument();
    expect(
      screen.getByText(/대화 2026-10-12 · “작년 3월부터” · '작년 3월' → 2025-03/),
    ).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: '고치기' }));
    expect(onEdit).toHaveBeenCalled();
  });

  it('직접 입력은 값을 보내고, 성공하면 입력칸을 닫는다', async () => {
    const onDirectSave = vi.fn().mockResolvedValue(undefined);
    render(
      <dl>
        <FieldRow label="회사명" value="OO산업" rawValue="OO산업" onDirectSave={onDirectSave} />
      </dl>,
    );

    await userEvent.click(screen.getByRole('button', { name: '직접 입력' }));
    const input = screen.getByLabelText('회사명 직접 입력');
    expect(input).toHaveValue('OO산업');
    await userEvent.clear(input);
    await userEvent.type(input, 'OO산업(주){Enter}');

    expect(onDirectSave).toHaveBeenCalledWith('OO산업(주)');
    expect(screen.queryByLabelText('회사명 직접 입력')).not.toBeInTheDocument();
  });

  it('서버가 값 정리에 실패하면 이유를 칸 아래에 보여 준다', async () => {
    const onDirectSave = vi
      .fn()
      .mockRejectedValue(
        new ApiError('VALIDATION_ERROR', '날짜는 2004-03처럼 연-월로 적어 주세요.', 422),
      );
    render(
      <dl>
        <FieldRow label="재직기간" rawValue="" onDirectSave={onDirectSave} />
      </dl>,
    );

    await userEvent.click(screen.getByRole('button', { name: '직접 입력' }));
    await userEvent.type(screen.getByLabelText('재직기간 직접 입력'), '2004년 봄');
    await userEvent.click(screen.getByRole('button', { name: '저장' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('연-월로 적어 주세요');
    expect(screen.getByLabelText('재직기간 직접 입력')).toBeInTheDocument();
  });

  it('글 한 칸으로 못 받는 칸은 편집기를 열고, 편집기가 닫으면 값 보기로 돌아온다', async () => {
    render(
      <dl>
        <FieldRow
          label="희망직종"
          value="아파트 전기관리원"
          editor={(close) => (
            <button type="button" onClick={close}>
              고르기 끝
            </button>
          )}
        />
      </dl>,
    );

    await userEvent.click(screen.getByRole('button', { name: '직접 입력' }));
    expect(screen.queryByText('아파트 전기관리원')).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: '고르기 끝' }));
    expect(screen.getByText('아파트 전기관리원')).toBeInTheDocument();
  });
});

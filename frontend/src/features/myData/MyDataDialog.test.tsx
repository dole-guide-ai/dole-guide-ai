import { screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { MyDataDialog } from '@/features/myData/MyDataDialog';

import { getFormDrafts, resetForms } from '@/lib/formStore';
import { MOCK_MY_DATA, MOCK_MY_DATA_DELETE_UPDATES, MOCK_NOT_STORED } from '@/mocks/myData';
import { renderWithProviders } from '@/test/renderWithProviders';

/** 지운 줄을 기억하는 작은 가짜 서버 */
const mockApi = () => {
  const deleted = new Set<string>();
  return vi.spyOn(globalThis, 'fetch').mockImplementation(async (input, init) => {
    const url = String(input);
    if (url.endsWith('/me/data') && init?.method === 'DELETE') {
      const { item_id } = JSON.parse(String(init.body)) as { item_id: string };
      deleted.add(item_id);
      return Response.json({ updates: MOCK_MY_DATA_DELETE_UPDATES[item_id] ?? [] });
    }
    if (url.endsWith('/me/data')) {
      return Response.json({
        items: MOCK_MY_DATA.lee.filter((item) => !deleted.has(item.item_id)),
        not_stored: MOCK_NOT_STORED,
      });
    }
    return Response.json({ code: 'NOT_FOUND', message: '없는 경로예요.' }, { status: 404 });
  });
};

describe('MyDataDialog', () => {
  beforeEach(() => resetForms());
  afterEach(() => vi.restoreAllMocks());

  it('확정된 값·절차 상태·확인한 사실과 저장하지 않는 정보를 보여 준다', async () => {
    mockApi();

    renderWithProviders(<MyDataDialog sessionId="s1" onClose={vi.fn()} />);

    expect(await screen.findByText('저장 완료 (일반 사무)')).toBeInTheDocument();
    const procedure = screen.getByRole('region', { name: '절차 상태' });
    expect(within(procedure).queryByRole('button', { name: /삭제/ })).not.toBeInTheDocument();
    // 실업크레딧 답·통지 방법 두 줄에 확인한 날짜가 붙습니다.
    expect(screen.getAllByText(/11\.24 확인/, { selector: 'span' })).toHaveLength(2);
    expect(screen.getByText(/저장하지 않는 정보 · 주민등록번호/)).toBeInTheDocument();
  });

  it('삭제하면 그 칸을 아직 없음으로 돌리고 목록에서 빠진다', async () => {
    mockApi();
    renderWithProviders(<MyDataDialog sessionId="s1" onClose={vi.fn()} />);

    await userEvent.click(await screen.findByRole('button', { name: '지급 결정 통지 방법 삭제' }));

    expect(await screen.findByRole('button', { name: '실업크레딧 답 삭제' })).toBeInTheDocument();
    await vi.waitFor(() =>
      expect(screen.queryByText('휴대전화 문자메시지')).not.toBeInTheDocument(),
    );
    expect(
      getFormDrafts().recognition.fields['notification_and_plan.payment_notification_method'],
    ).toMatchObject({ status: 'missing' });
  });

  it('Esc로 닫는다', async () => {
    mockApi();
    const onClose = vi.fn();
    renderWithProviders(<MyDataDialog sessionId="s1" onClose={onClose} />);

    await userEvent.keyboard('{Escape}');

    expect(onClose).toHaveBeenCalledTimes(1);
  });
});

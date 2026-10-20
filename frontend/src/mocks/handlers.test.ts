import { beforeEach, describe, expect, it } from 'vitest';

import { ApiError } from '@/lib/api';
import type { FormPatchRead } from '@/types/chat.types';
import type { PersonaCardRead, SessionRead } from '@/types/demo.types';
import type { RoundCheckRead } from '@/types/procedure.types';
import type { RecognitionFormRead } from '@/types/recognition.types';
import { resetMockAuth, resolveMock } from '@/mocks/handlers';

describe('모의 API', () => {
  beforeEach(() => resetMockAuth());

  it('계정 목록은 카드 표시용 값만 돌려준다', async () => {
    const cards = await resolveMock<PersonaCardRead[]>('/auth/demo');

    expect(cards.map((card) => card.persona_id)).toEqual(['park', 'choi', 'lee']);
    expect(cards[0]).not.toHaveProperty('state');
  });

  it('계정을 고르기 전에는 세션을 만들 수 없다', async () => {
    await expect(resolveMock('/sessions', { method: 'POST' })).rejects.toBeInstanceOf(ApiError);
  });

  it('이정호를 고르면 E4b 진입 결과가 나온다', async () => {
    await resolveMock('/auth/demo', {
      method: 'POST',
      body: JSON.stringify({ persona_id: 'lee' }),
    });
    const session = await resolveMock<SessionRead>('/sessions', { method: 'POST' });

    expect(session.entry.branch_id).toBe('E4b');
    expect(session.entry.panel).toBe('B');
    expect(session.derived.d_day).toBe(6);
    expect(session.entry.choices).toHaveLength(3);
  });

  it('최영수는 글자 크게가 기본으로 켜진다 (M4)', async () => {
    await resolveMock('/auth/demo', {
      method: 'POST',
      body: JSON.stringify({ persona_id: 'choi' }),
    });
    const session = await resolveMock<SessionRead>('/sessions', { method: 'POST' });

    expect(session.entry.branch_id).toBe('E7b');
    expect(session.entry.ui.big_text).toBe(true);
  });

  it('이정호 회차 점검과 추천 선택(PATCH /procedure)은 예정 활동 form_update를 돌려준다', async () => {
    await resolveMock('/auth/demo', {
      method: 'POST',
      body: JSON.stringify({ persona_id: 'lee' }),
    });
    const check = await resolveMock<RoundCheckRead>('/procedure/current-round/check');
    const { updates } = await resolveMock<FormPatchRead>('/procedure', {
      method: 'PATCH',
      body: JSON.stringify({
        path: 'activities',
        op: 'append',
        value: { recommendation_id: 'rec_step_online' },
      }),
    });

    expect(check.shortfall).toBe(1);
    expect(updates[0]).toMatchObject({
      form: 'activities',
      op: 'append',
      value: { item_id: 'planned_rec_step_online', status: 'planned' },
    });
    await expect(
      resolveMock('/procedure', {
        method: 'PATCH',
        body: JSON.stringify({ path: 'x', op: 'set' }),
      }),
    ).rejects.toMatchObject({ code: 'VALIDATION_ERROR' });
  });

  it('이정호 4차 신청서는 출석 모드이고, 모드가 맞을 때만 모의 확정된다', async () => {
    await resolveMock('/auth/demo', {
      method: 'POST',
      body: JSON.stringify({ persona_id: 'lee' }),
    });
    const form = await resolveMock<RecognitionFormRead>('/forms/recognition');
    const confirmed = await resolveMock<RecognitionFormRead>('/forms/recognition/confirm', {
      method: 'POST',
      body: JSON.stringify({ submit_mode: 'attend' }),
    });

    expect(form.submit_mode).toBe('attend');
    expect(form.work_and_employment.has_work_or_service).toBeNull();
    expect(confirmed).toMatchObject({ status: 'finalized', mock_submission: 'attend_ready' });
    await expect(
      resolveMock('/forms/recognition/confirm', {
        method: 'POST',
        body: JSON.stringify({ submit_mode: 'send' }),
      }),
    ).rejects.toMatchObject({ code: 'CONFLICT' });
  });
});

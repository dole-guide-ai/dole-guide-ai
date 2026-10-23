import { beforeEach, describe, expect, it } from 'vitest';

import { sessionFromAccount } from '@/lib/accountSession';
import { ApiError } from '@/lib/api';
import { applyFormUpdate, resetForms } from '@/lib/formStore';
import { roundCheckFromServer } from '@/lib/roundCheck';
import { setSession } from '@/lib/sessionStore';
import type { components } from '@/types/api.gen';
import type { SessionRead } from '@/types/demo.types';
import type { RecognitionFormRead } from '@/types/recognition.types';
import { resetMockAuth, resolveMock } from '@/mocks/handlers';
import { LEE_ROUND_CHECK } from '@/test/roundCheckFixture';

type AccountRead = components['schemas']['AccountRead'];

const enter = async (personaId: string) =>
  sessionFromAccount(await resolveMock<AccountRead>(`/accounts/${personaId}`, { method: 'PUT' }));

describe('모의 API', () => {
  beforeEach(() => resetMockAuth());

  it('계정 목록은 카드 표시용 값만 돌려준다', async () => {
    const cards = await resolveMock<components['schemas']['PersonaList']>('/personas');

    expect(cards.items.map((card) => card.persona_id)).toEqual(['park', 'choi', 'lee']);
    expect(cards.items[0]).not.toHaveProperty('state');
  });

  const leeActivities = roundCheckFromServer(LEE_ROUND_CHECK).activities;

  it('신청서 초안은 패널 B에 기록된 활동으로 재취업 활동정보를 채운다 (시연 검증 1번)', async () => {
    await resolveMock('/accounts/lee', { method: 'PUT' });
    applyFormUpdate({
      form: 'activities',
      path: 'activities',
      op: 'set',
      value: [
        ...leeActivities,
        {
          ...leeActivities[0],
          item_id: 'a5',
          date: '2026-12-11',
          route: 'interview',
          org_name: 'OO서비스',
          source: 'document',
        },
        {
          ...leeActivities[0],
          item_id: 'a6',
          date: '2026-12-14',
          kind: 'other',
          route: 'step_online',
          org_name: '고용24 온라인 취업특강',
        },
      ],
    });

    const form = await resolveMock<RecognitionFormRead>('/forms/recognition');
    const activity = form.reemployment_activity;

    expect(activity.job_search_activities.map((job) => job.company_name)).toEqual([
      'OO물류',
      'OO서비스',
    ]);
    expect(activity.job_search_activities[1]).toMatchObject({
      application_method: '직접방문',
      activity_result: '면접을 본 후 결과를 기다리는 중',
    });
    expect(activity.excluded.map((item) => item.company_name)).toEqual(['OO상사']);
    expect(activity.other_reemployment_activities[0]).toMatchObject({
      course: '취업특강(온라인, 오프라인) 수강',
    });
    resetForms();
  });

  it('이력서를 저장해도 세션 ID는 그대로다 (시연 검증 4번: 닫은 토스트가 다시 뜨지 않게)', async () => {
    const session = await enter('choi');
    setSession(session);

    const saved = await resolveMock<SessionRead>('/forms/resume/confirm', {
      method: 'POST',
      body: '{}',
    });

    expect(saved.session_id).toBe(session.session_id);
    expect(saved.state.stage).toBe('education');
    setSession(null);
  });

  it('없는 계정으로는 입장할 수 없다', async () => {
    await expect(resolveMock('/accounts/nobody', { method: 'PUT' })).rejects.toBeInstanceOf(
      ApiError,
    );
  });

  it('이정호를 고르면 E4b 진입 결과가 나온다', async () => {
    const session = await enter('lee');

    expect(session.entry.branch_id).toBe('E4b');
    expect(session.entry.panel).toBe('B');
    expect(session.derived.d_day).toBe(6);
    expect(session.entry.choices).toHaveLength(3);
  });

  it('최영수는 글자 크게가 기본으로 켜진다 (M4)', async () => {
    const session = await enter('choi');

    expect(session.entry.branch_id).toBe('E7b');
    expect(session.entry.ui.big_text).toBe(true);
  });

  it('이정호 4차 신청서는 출석 모드이고, 모드가 맞을 때만 모의 확정된다', async () => {
    await resolveMock('/accounts/lee', { method: 'PUT' });
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

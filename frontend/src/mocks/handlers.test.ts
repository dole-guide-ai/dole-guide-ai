import { beforeEach, describe, expect, it } from 'vitest';

import { sessionFromAccount } from '@/lib/accountSession';
import { ApiError } from '@/lib/api';
import { applyFormUpdate, resetForms } from '@/lib/formStore';
import { setSession } from '@/lib/sessionStore';
import type { components } from '@/types/api.gen';
import type { FormPatchRead } from '@/types/chat.types';
import type { SessionRead } from '@/types/demo.types';
import type { ImportListRead } from '@/types/imports.types';
import type { RoundCheckRead } from '@/types/procedure.types';
import type { RecognitionFormRead } from '@/types/recognition.types';
import { MOCK_ROUND_CHECKS } from '@/mocks/activities';
import { resetMockAuth, resolveMock } from '@/mocks/handlers';

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

  it('신청서 초안은 패널 B에 기록된 활동으로 재취업 활동정보를 채운다 (시연 검증 1번)', async () => {
    await resolveMock('/accounts/lee', { method: 'PUT' });
    applyFormUpdate({
      form: 'activities',
      path: 'activities',
      op: 'set',
      value: [
        ...MOCK_ROUND_CHECKS.lee.activities,
        {
          ...MOCK_ROUND_CHECKS.lee.activities[0],
          item_id: 'a5',
          date: '2026-12-11',
          route: 'interview',
          org_name: 'OO서비스',
          source: 'document',
        },
        {
          ...MOCK_ROUND_CHECKS.lee.activities[0],
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

  it('다시 불러오기에서는 이미 넣은 항목을 `이미 넣음`으로 막는다 (시연 검증 13번)', async () => {
    await resolveMock('/accounts/park', { method: 'PUT' });
    applyFormUpdate({
      form: 'resume',
      path: 'competencies.vocational_training',
      op: 'set',
      value: [{ item_id: 'training_001', name: '용접 기초 과정' }],
    });

    const list = await resolveMock<ImportListRead>('/imports/career-certificate');

    expect(list.items.map((item) => [item.title, item.is_recorded])).toEqual([
      ['OO산업', false],
      ['지게차운전기능사', false],
      ['용접 기초 과정', true],
    ]);
    resetForms();
  });

  it('패널 버튼으로 교육 이수를 넣으면 대화 대본과 같은 단계 전환을 돌려준다 (F-16)', async () => {
    const res = await resolveMock<{ updates: { form: string; path: string; value: unknown }[] }>(
      '/accounts/choi/procedure',
      {
        method: 'PATCH',
        body: JSON.stringify([{ op: 'replace', path: '/education_done', value: true }]),
      },
    );

    const state = res.updates.find((update) => update.path === 'state');
    expect(state?.value).toMatchObject({ stage: 'eligibility_application', education_done: true });
    expect(res.updates).toContainEqual(
      expect.objectContaining({ path: 'entry.panel', value: 'Q' }),
    );
    await expect(
      resolveMock('/accounts/choi/procedure', {
        method: 'PATCH',
        body: JSON.stringify([{ op: 'replace', path: '/stage', value: 'x' }]),
      }),
    ).rejects.toMatchObject({ status: 422 });
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

  it('이정호 회차 점검과 추천 선택(PATCH /procedure)은 예정 활동 form_update를 돌려준다', async () => {
    await resolveMock('/accounts/lee', { method: 'PUT' });
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

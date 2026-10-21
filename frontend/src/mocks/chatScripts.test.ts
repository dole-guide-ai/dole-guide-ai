import { beforeEach, describe, expect, it } from 'vitest';

import { OPEN_FORM_MESSAGE } from '@/features/procedure/activityLabels';

import { applyFormUpdate, resetForms } from '@/lib/formStore';
import type { FormUpdateEvent, SseMessage } from '@/types/chat.types';
import { buildMockChatEvents, resetMockChat } from '@/mocks/chatScripts';

const updates = (events: SseMessage[]): FormUpdateEvent[] =>
  events.flatMap((event) => (event.event === 'form_update' ? [event.data] : []));

const lastAsk = (events: SseMessage[]) => [...events].reverse().find((e) => e.event === 'ask_user');

const text = (events: SseMessage[]) =>
  events.map((event) => (event.event === 'token' ? event.data.text : '')).join('');

/** 화면처럼 양식 갱신을 저장소에 반영하며 한 턴을 보냅니다 (다음 턴이 지금 값을 읽도록). */
const send = (personaId: string, message: string, imports?: string[], files?: string[]) => {
  const events = buildMockChatEvents(personaId, message, ['처음 선택지'], files, imports);
  updates(events)
    .filter((update) => update.form !== 'procedure')
    .forEach(applyFormUpdate);
  return events;
};

beforeEach(() => {
  resetForms();
  resetMockChat();
});

describe('이정호 신청서 모의 대화', () => {
  it('신청서 만들기는 패널을 C로 바꾸고 근로·소득 질문부터 한다 (2-3.3)', () => {
    const events = buildMockChatEvents('lee', OPEN_FORM_MESSAGE, []);

    expect(updates(events)).toContainEqual(
      expect.objectContaining({ form: 'procedure', path: 'entry.panel', value: 'C' }),
    );
    expect(events.at(-1)).toMatchObject({
      event: 'ask_user',
      data: { choices: ['없어요', '있어요', '잘 모르겠어요'] },
    });
  });

  it('신청서 정리 말풍선은 패널 B에 기록된 활동 수를 그대로 말한다 (시연 검증 1번)', () => {
    applyFormUpdate({
      form: 'activities',
      path: 'activities',
      op: 'set',
      value: [
        {
          item_id: 'a1',
          kind: 'job_search',
          route: 'work24',
          org_name: 'OO물류',
          status: 'counted',
        },
        {
          item_id: 'a2',
          kind: 'job_search',
          route: 'company_site',
          org_name: 'OO상사',
          status: 'same_day',
        },
        {
          item_id: 'a5',
          kind: 'job_search',
          route: 'interview',
          org_name: 'OO서비스',
          status: 'counted',
        },
        { item_id: 'a6', kind: 'other', route: 'step_online', org_name: '특강', status: 'counted' },
      ],
    });

    const said = text(buildMockChatEvents('lee', '신청서 볼게요', []));

    expect(said).toContain('구직활동 2건을 구직활동내역에 옮겼어요');
    expect(said).toContain('구직 외 활동 1건');
    expect(said).toContain('같은 날이라 뺀 활동(OO상사)');
  });

  it('고용24에서 지원하러 가면 지원한 뒤 누를 선택지를 준다 (시연 검증 6번)', () => {
    const events = buildMockChatEvents('lee', '고용24에서 지원하러 갈게요', []);

    expect(lastAsk(events)).toMatchObject({
      data: { choices: ['방금 고용24로 OO물산에 지원했어요', '이미 한 활동 기록할게요'] },
    });
  });

  it('면접·온라인 취업특강은 기준일(12.16) 이전 날짜로 기록한다 (시연 검증 2번)', () => {
    send('lee', '면접 봤어요');
    const interview = send('lee', '파일을 올렸어요. 읽어 주세요.', undefined, ['f1']);
    const step = send('lee', '네, 끝까지 들었어요');
    const dates = [...updates(interview), ...updates(step)]
      .filter((update) => update.path === 'activities' && update.op === 'append')
      .map((update) => (update.value as { date: string }).date);

    expect(dates).toEqual(['2026-12-11', '2026-12-14']);
  });

  it('다음 실업인정일을 알려 주면 5차로 넘어간다 (평가 form-005)', () => {
    const events = buildMockChatEvents('lee', '다음은 1월 19일이래요', []);
    const byPath = Object.fromEntries(updates(events).map((update) => [update.path, update.value]));

    expect(byPath.state).toMatchObject({
      completed_rounds: 4,
      next_recognition_date: '2027-01-19',
      demo_today: '2026-12-22',
    });
    expect(byPath.derived).toMatchObject({ current_round: 5, d_day: 28 });
    expect(byPath['entry.panel']).toBe('B');
  });

  it('고용24에서 불러올게요는 입사지원 목록을 열고, 고른 OO물산은 활동으로 기록된다 (2-2.5)', () => {
    const open = buildMockChatEvents('lee', '고용24에서 불러올게요', []);
    const recorded = buildMockChatEvents(
      'lee',
      '고용24에서 고른 1건 넣어 주세요',
      [],
      [],
      ['wa_003'],
    );

    expect(open.at(-1)).toMatchObject({
      event: 'ask_user',
      data: { import_kind: 'work24-activities' },
    });
    expect(updates(recorded)).toContainEqual(
      expect.objectContaining({ form: 'activities', path: 'activities', op: 'append' }),
    );
  });
});

describe('박진수 통합경력증명 불러오기', () => {
  it('고른 경력·직업훈련만 넣고, 직급을 이어서 묻는다 (2-1.5)', () => {
    const events = buildMockChatEvents(
      'park',
      '고용24에서 고른 2건 넣어 주세요',
      [],
      [],
      ['cc_career_001', 'cc_training_001'],
    );
    const paths = updates(events).map((update) => update.path);

    expect(paths).toContain('competencies.careers');
    expect(paths).toContain('competencies.vocational_training');
    expect(paths).not.toContain('competencies.certifications');
    expect(updates(events).find((u) => u.path.endsWith('company_name'))).toMatchObject({
      source: 'work24_import',
    });
    expect(events.at(-1)).toMatchObject({
      event: 'ask_user',
      data: { choices: ['직급 말할게요', '없었어요'] },
    });
  });

  it('이정호가 지원 완료 캡처를 올리면 활동 1건을 더하고 충족으로 바뀐다 (2-2.5)', () => {
    const events = buildMockChatEvents('lee', '사진을 올렸어요. 읽어 주세요.', [], ['file-1']);
    const byPath = Object.fromEntries(updates(events).map((update) => [update.path, update]));

    expect(byPath.activities).toMatchObject({
      op: 'append',
      value: { org_name: 'OO기획', evidence: { attached: ['지원완료_캡처.png'] } },
    });
    expect(byPath.status).toMatchObject({ value: 'satisfied' });
  });

  it('근로 있음은 일한 날부터 금액까지 묻고, 취업했다고 하면 신청서를 잠근다 (2-3.3)', () => {
    const started = buildMockChatEvents('lee', '있어요', []);
    const finished = buildMockChatEvents('lee', '10만 원이요', []);
    const locked = buildMockChatEvents('lee', '네, 취업했어요', []);

    expect(started.at(-1)).toMatchObject({ data: { question_id: 'form.work_dates' } });
    expect(updates(finished)).toContainEqual(
      expect.objectContaining({
        path: 'work_and_employment.work_details.income_amount',
        value: 100000,
        source: 'self_answer',
      }),
    );
    expect(updates(locked)).toContainEqual(
      expect.objectContaining({ path: 'locked_reason', value: 'employment' }),
    );
  });
});

describe('시연 개선 (2026-10-21 피드백)', () => {
  it('준비되지 않은 답에는 첫 화면이 아니라 직전 질문을 다시 보여 준다 (점검 6)', () => {
    send('choi', '네, 고칠게요');
    const events = send('choi', '없어요');

    expect(text(events)).toContain('시연 대화가 아직 준비되지 않았어요');
    expect(lastAsk(events)).toMatchObject({
      data: { question_id: 'resume.career_since_old', choices: ['네, 있어요', '없어요'] },
    });
  });

  it('불러오기 뒤 직급 없음 → 주요 직무 → 자격면허로 이어진다 (시연 개선 10번, 점검 2)', () => {
    send('park', '고용24에서 고른 2건 넣어 주세요', ['cc_career_001', 'cc_training_001']);
    const duties = send('park', '없었어요');
    expect(updates(duties)).toContainEqual(
      expect.objectContaining({ path: 'competencies.careers.career_001.position', value: '없음' }),
    );
    expect(lastAsk(duties)).toMatchObject({
      data: { question_id: 'resume.career_duties.career_001' },
    });

    const next = send('park', '프레스 라인을 돌렸어요');
    expect(updates(next)).toContainEqual(
      expect.objectContaining({ path: 'competencies.careers.career_001.main_duties' }),
    );
    expect(lastAsk(next)).toMatchObject({
      data: { question_id: 'resume.license', accepts_file: true },
    });
  });

  it('경력 없이 직업훈련만 넣으면 경력 질문을 파일 요청과 함께 잇는다 (시연 개선 10번)', () => {
    const events = send('park', '고용24에서 고른 1건 넣어 주세요', ['cc_training_001']);

    expect(text(events)).toContain('고르신 항목을 넣었어요: 직업훈련 이수이력(용접 기초 과정).');
    expect(lastAsk(events)).toMatchObject({
      data: { question_id: 'resume.career_new', accepts_file: true },
    });
  });

  it('사진 뒤 주로 한 일을 말해도 경력이 하나뿐이고 날짜 확인 질문이 나오지 않는다 (시연 개선 11번)', () => {
    send('park', '파일을 올렸어요. 읽어 주세요.', undefined, ['file-1']);
    const events = send('park', '프레스 기계를 돌리고 불량품을 검사했어요');

    expect(text(events)).not.toContain('작년 3월');
    expect(lastAsk(events)).toMatchObject({
      data: { question_id: 'resume.career_position.career_001' },
    });
  });

  it('박진수 학력 질문에서 시연이 끝났다고 알린다 (시연 개선 1번)', () => {
    send('park', 'OO산업에서 2004년 3월부터 프레스 반장으로 일했어요');
    send('park', '네, 맞아요');
    send('park', '없어요');
    const events = send('park', '고등학교 졸업');

    expect(text(events)).toContain('(박진수 시연은 여기까지예요.');
  });

  it('이정호 활동 기록은 종류부터 고르고, 면접확인서를 올리면 면접 1건이 들어간다 (시연 개선 13번)', () => {
    const kinds = send('lee', '이미 한 활동 기록할게요');
    expect(lastAsk(kinds)).toMatchObject({
      data: { choices: expect.arrayContaining(['면접 봤어요', '그 밖의 활동이에요']) },
    });

    const ask = send('lee', '면접 봤어요');
    expect(lastAsk(ask)).toMatchObject({ data: { accepts_file: true } });

    const recorded = send('lee', '파일을 올렸어요. 읽어 주세요.', undefined, ['file-2']);
    expect(updates(recorded)).toContainEqual(
      expect.objectContaining({
        path: 'activities',
        op: 'append',
        value: expect.objectContaining({ category: '면접', org_name: 'OO서비스' }),
      }),
    );
  });

  it('최영수는 교육 이수 → 방문 신청 → 1차 실업인정일까지 가고 끝을 알린다 (시연 개선 12번)', () => {
    send('choi', '교육 다 들었어요');
    const eligibility = send('choi', '네, 이수했어요');
    expect(updates(eligibility)).toContainEqual(
      expect.objectContaining({ form: 'procedure', path: 'entry.panel', value: 'Q' }),
    );

    const applied = send('choi', '방문 신청했어요');
    expect(updates(applied)).toContainEqual(
      expect.objectContaining({
        form: 'procedure',
        path: 'entry.title',
        value: '1차 실업인정일을 알려 주세요',
      }),
    );
    expect(lastAsk(applied)).toMatchObject({ data: { accepts_file: true } });

    const first = send('choi', '1차 실업인정일은 11월 4일이래요');
    expect(updates(first)).toContainEqual(
      expect.objectContaining({
        form: 'procedure',
        path: 'derived',
        value: expect.objectContaining({ current_round: 1, d_day: 23 }),
      }),
    );
    expect(text(first)).toContain('(최영수 시연은 여기까지예요.');
  });

  it('5차 첫 화면에서 이정호 시연이 끝났다고 알린다 (시연 개선 1번)', () => {
    const events = send('lee', '다음은 1월 19일이래요');

    expect(text(events)).toContain('(이정호 시연은 여기까지예요.');
  });

  it('활동 추천 목록은 줄을 바꿔 보여 준다 (시연 개선 3번)', () => {
    const events = send('lee', '부족한 활동 추천해 주세요');

    expect(text(events)).toContain('\n1) 고용24로 희망 직종 공고에 입사지원');
  });
});

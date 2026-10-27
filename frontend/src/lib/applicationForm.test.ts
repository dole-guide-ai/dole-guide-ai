import { describe, expect, it } from 'vitest';

import { recognitionFromApplication } from '@/lib/applicationForm';
import type { components } from '@/types/api.gen';

type ApplicationRead = components['schemas']['ApplicationRead'];

const answered = (value: string) => ({
  value,
  status: 'confirmed' as const,
  source: 'user_answer' as const,
  transformed: false,
  answered_on: '2026-11-24',
});
const empty = () => ({ status: 'missing' as const, transformed: false });

const application = (overrides: Partial<ApplicationRead> = {}): ApplicationRead => ({
  round: 4,
  status: 'draft',
  lock_version: 1,
  period_start: '2026-11-25',
  period_end: '2026-12-22',
  recognition_date: '2026-12-22',
  attendance_required: true,
  required_activities: 2,
  counted_activities: 1,
  counted_job_search: 1,
  remaining_activities: 1,
  remaining_job_search: 0,
  required_job_search: 1,
  data: {
    work: { has_work: empty(), entries: empty() },
    employment: { status: empty(), started_on: empty() },
    industrial_accident: { receiving: empty() },
    credit: {
      application: answered('wish'),
      notice_method: answered('electronic'),
      auto_payment: answered('not_wish'),
      income_asset_consent: answered('agree'),
    },
    notification_method: answered('sms'),
    next_plan: empty(),
    privacy_consent: empty(),
  },
  job_search_rows: [
    {
      activity_id: 'a1',
      activity_date: '2026-12-08',
      company_name: 'OO물류',
      application_method: '고용24(워크넷)',
      job_search_method: '고용24(워크넷)',
      file_ids: [],
    },
  ],
  other_rows: [],
  excluded_rows: [
    { activity_id: 'a2', reason: 'same_day', activity_date: '2026-12-08', company_name: 'OO상사' },
  ],
  checklist: { blocking: [{ key: 'self_answers', text: '본인 답변' }], warnings: [] },
  submit_mode: 'preview',
  can_submit: false,
  ...overrides,
});

describe('recognitionFromApplication (F-23)', () => {
  it('회차 정보·구직활동 줄·같은 날 뺀 활동을 패널 C 모양으로 옮긴다', () => {
    const form = recognitionFromApplication(application());

    expect(form.recognition_round).toBe(4);
    expect(form.recognition_info).toEqual({
      recognition_date: '2026-12-22',
      period_start: '2026-11-25',
      period_end: '2026-12-22',
      attendance_round: true,
    });
    expect(form.reemployment_activity.required).toEqual({ activities: 2, job_search: 1 });
    expect(form.reemployment_activity.job_search_activities.map((a) => a.company_name)).toEqual([
      'OO물류',
    ]);
    expect(form.reemployment_activity.job_search_activities[0].source).toBe('work24_import');
    expect(form.reemployment_activity.excluded).toEqual([
      { item_id: 'a2', reason: 'same_day', activity_date: '2026-12-08', company_name: 'OO상사' },
    ]);
    expect(form.attend_items).toEqual(['id_card', 'eligibility_card']);
    expect(form.checklist).toHaveLength(7);
    expect(form.checklist[0]).toEqual({ key: 'self_answers', done: false, blocking: true });
    expect(form.checklist.filter((item) => !item.done).map((item) => item.key)).toEqual([
      'self_answers',
    ]);
  });

  it('선택지 코드를 고용24 화면 글자로 바꾸고, 지난 회차 답에는 지난 답 칸 상태를 붙인다', () => {
    const form = recognitionFromApplication(application());

    expect(form.unemployment_credit).toMatchObject({
      credit_application_choice: '희망함',
      notice_delivery_method: '전자고지',
      automatic_payment_choice: '희망하지 않음',
      income_asset_consent: '동의함',
      answered_on: '2026-11-24',
    });
    expect(form.notification_and_plan.payment_notification_method).toBe('휴대전화 문자메시지');
    expect(form.field_states['notification_and_plan.payment_notification_method']).toMatchObject({
      source: 'user_answer',
      evidence: { kind: 'previous_round', date: '2026-11-24' },
    });
    expect(form.work_and_employment.has_work_or_service).toBeNull();
  });

  it('취업 잠금과 제출된 회차를 바꾼다', () => {
    const form = recognitionFromApplication(
      application({ status: 'submitted', locked_reason: 'employed' }),
    );

    expect(form.locked_reason).toBe('employment');
    expect(form.status).toBe('finalized');
    expect(form.mock_submission).toBe('attend_ready');
  });
});

describe('recognitionFromApplication 답변 변환', () => {
  it('이번 회차에 답한 값에는 지난 답 칩을 붙이지 않는다', () => {
    const form = recognitionFromApplication(
      application({
        data: {
          ...application().data,
          notification_method: { ...answered('sms'), answered_on: '2026-12-01' },
        },
      }),
    );

    expect(form.field_states['notification_and_plan.payment_notification_method']).toEqual({
      status: 'confirmed',
      source: 'user_answer',
    });
  });

  it('근로내역 여러 건을 모두 옮기고, 다음 활동·필수만 동의를 그대로 보여 준다', () => {
    const base = application().data;
    const form = recognitionFromApplication(
      application({
        data: {
          ...base,
          work: {
            has_work: answered('yes'),
            entries: answered([
              {
                worked_on: '2026-12-05',
                hours: 4,
                income_received_on: '2026-12-10',
                amount: 40000,
              },
              {
                worked_on: '2026-12-12',
                hours: 5,
                income_received_on: '2026-12-17',
                amount: 50000,
              },
            ] as unknown as string),
          },
          next_plan: answered([
            { item_id: 'p1', kind: 'job_search', planned_on: '2026-12-29' },
            { item_id: 'p2', kind: 'job_search', planned_on: '2026-12-30' },
            { item_id: 'p3', kind: 'lecture', planned_on: '2027-01-04' },
          ] as unknown as string),
          privacy_consent: answered('agree_required_only'),
        },
      }),
    );

    expect(form.work_and_employment.work_entries?.map((w) => w.income_amount)).toEqual([
      40000, 50000,
    ]);
    expect(form.notification_and_plan.next_activity).toEqual({
      value: '구직활동 12.29(화), 구직활동 12.30(수), 취업특강(온라인, 오프라인) 수강 1.4(월)',
      memo: null,
      answered_on: '2026-11-24',
    });
    expect(form.personal_information_consent.value).toBe('agree_required_only');
  });

  it('서버가 준 본인 답변을 칸 상태로 옮기고, 답하지 않은 칸은 비워 둔다', () => {
    const base = application().data;
    const form = recognitionFromApplication(
      application({
        data: {
          ...base,
          work: { has_work: { ...answered('no'), answered_on: '2026-12-16' }, entries: empty() },
        },
      }),
    );

    expect(form.field_states['work_and_employment.has_work_or_service']).toEqual({
      status: 'confirmed',
      source: 'user_answer',
    });
    expect(form.field_states['work_and_employment.has_employment']).toBeUndefined();
  });

  it('빈 다음 활동과 일부 칸이 빠진 근로내역은 답한 것으로 보지 않는다', () => {
    const base = application().data;
    const form = recognitionFromApplication(
      application({
        data: {
          ...base,
          work: {
            has_work: answered('yes'),
            entries: answered([
              { worked_on: '2026-12-05', income_received_on: '2026-12-10', amount: 40000 },
            ] as unknown as string),
          },
          next_plan: answered([] as unknown as string),
        },
      }),
    );

    expect(form.field_states['notification_and_plan.next_activity']).toBeUndefined();
    expect(form.field_states['work_and_employment.work_details.total_hours']).toBeUndefined();
    expect(form.field_states['work_and_employment.work_details.work_dates']).toMatchObject({
      status: 'confirmed',
    });
  });
});

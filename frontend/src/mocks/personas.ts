import type { components } from '@/types/api.gen';
import type { DerivedState, UserState } from '@/types/demo.types';

type PersonaDisplay = components['schemas']['PersonaDisplay'];

/**
 * 시연용 가상 계정 seed (상세기획 1.9). 날짜·회사·인물은 모두 가상 값입니다.
 * 모의 모드(`NEXT_PUBLIC_USE_MOCK=1`) 전용. 실제 값은 백엔드 `data/seeds/personas.json`입니다.
 */
export interface MockPersona {
  persona_id: string;
  display: PersonaDisplay;
  state: UserState;
  derived: DerivedState;
}

export const MOCK_PERSONAS: MockPersona[] = [
  {
    persona_id: 'park',
    display: {
      name: '박진수',
      age: 61,
      job: '생산직 · 프레스',
      quote: '컴퓨터는 잘 못 해요. 이력서를 어디서부터 써야 할지 모르겠어요.',
      summary: '구직등록 전 · 이력서 없음',
    },
    state: {
      separation_date: '2026-09-30',
      age_at_separation: 61,
      has_disability: false,
      recipient_type: 'general',
      employment_type: 'regular',
      stage: 'job_registration',
      resume_status: 'none',
      education_done: false,
      eligibility_applied_date: null,
      completed_rounds: 0,
      last_recognition_date: null,
      next_recognition_date: null,
      demo_today: '2026-10-12',
      demo_time: '10:00',
    },
    derived: {
      rule_group: 'age_60_64',
      rule_set: null,
      current_round: null,
      d_day: null,
      period: null,
      is_attendance_round: false,
      required: null,
      required_job_search: null,
      can_presubmit_online: true,
    },
  },
  {
    persona_id: 'choi',
    display: {
      name: '최영수',
      age: 67,
      job: '시설관리',
      quote: '예전에 써 둔 이력서가 있는데, 그걸 그대로 쓰면 되는 건가요?',
      summary: '구직등록 전 · 예전 이력서 최신화',
    },
    state: {
      separation_date: '2026-09-30',
      age_at_separation: 67,
      has_disability: false,
      recipient_type: 'general',
      employment_type: 'regular',
      stage: 'job_registration',
      resume_status: 'outdated',
      education_done: false,
      eligibility_applied_date: null,
      completed_rounds: 0,
      last_recognition_date: null,
      next_recognition_date: null,
      demo_today: '2026-10-12',
      demo_time: '10:00',
    },
    derived: {
      rule_group: 'age65_or_disabled',
      rule_set: null,
      current_round: null,
      d_day: null,
      period: null,
      is_attendance_round: false,
      required: null,
      required_job_search: null,
      can_presubmit_online: false,
    },
  },
  {
    persona_id: 'lee',
    display: {
      name: '이정호',
      age: 58,
      job: '일반 사무 · 행정지원',
      quote:
        '회사에 지원은 했는데 증빙을 뭘 올려야 하는지, 이번 회차에 몇 번 했는지 기억이 안 납니다.',
      summary: '수급 중 · 4차 실업인정 준비 · 이력서 있음',
    },
    state: {
      separation_date: '2026-08-31',
      age_at_separation: 58,
      has_disability: false,
      recipient_type: 'general',
      employment_type: 'regular',
      stage: 'recognition',
      resume_status: 'ready',
      education_done: true,
      eligibility_applied_date: '2026-09-15',
      completed_rounds: 3,
      last_recognition_date: '2026-11-24',
      next_recognition_date: '2026-12-22',
      demo_today: '2026-12-16',
      demo_time: '10:00',
    },
    derived: {
      rule_group: 'general',
      rule_set: '2026 안내문 기준',
      current_round: 4,
      d_day: 6,
      period: { start: '2026-11-25', end: '2026-12-22' },
      is_attendance_round: true,
      required: 2,
      required_job_search: 1,
      can_presubmit_online: true,
    },
  },
];

export const findMockPersona = (personaId: string) =>
  MOCK_PERSONAS.find((persona) => persona.persona_id === personaId);

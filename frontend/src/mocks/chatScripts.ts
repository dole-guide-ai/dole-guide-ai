import { OPEN_FORM_MESSAGE } from '@/features/procedure/activityLabels';
import { CONFIRMED_MESSAGE } from '@/features/recognition/recognitionLabels';

import type { FormUpdateEvent, SseMessage } from '@/types/chat.types';
import type { ImportKind } from '@/types/imports.types';

import { MOCK_PERSONAS } from './personas';

/**
 * 모의 대화 스크립트. 선택지·짧은 말에 대한 응답을 상세기획 문구로 미리 적어 둔다.
 * 실제 LLM·규칙 함수는 백엔드가 맡고, 여기서는 이벤트 순서(token → form_update → ask_user → done)만 흉내 낸다.
 */
const SOURCE_WORK24 = '고용24 실업급여(상용직)';
const SOURCE_2026_NOTICE = '실업인정 인정기준 안내문(2026.3.1~ 신청자) · 취업드림수첩 2025';

const TOKEN_SIZE = 6;

const tokens = (text: string): SseMessage[] => {
  const chunks: SseMessage[] = [];
  for (let i = 0; i < text.length; i += TOKEN_SIZE) {
    chunks.push({ event: 'token', data: { text: text.slice(i, i + TOKEN_SIZE) } });
  }
  return chunks;
};

const say = (text: string, cite?: string, rule_refs?: string[]): SseMessage[] => [
  ...tokens(text),
  { event: 'done', data: { cite, rule_refs } },
];

const ask = (
  question_id: string,
  text: string,
  choices: string[],
  import_kind?: ImportKind,
): SseMessage => ({
  event: 'ask_user',
  data: { question_id, text, choices, ...(import_kind ? { import_kind } : {}) },
});

/** 고용24 불러오기 목록을 대화창 안에 엽니다 (2-0.4). 고른 것만 `import_ids`로 돌아옵니다. */
const openImport = (kind: ImportKind, text: string): SseMessage[] => [
  ask(`import.${kind}`, text, [], kind),
];

const CAREER_IMPORT_TEXT = '통합경력증명에서 이력서에 넣을 항목을 골라 주세요. 고른 것만 넣어요.';

const tool = (name: string): SseMessage[] => [
  { event: 'tool_call', data: { name, status: 'started' } },
  { event: 'tool_call', data: { name, status: 'finished' } },
];

type UpdateExtra = Omit<FormUpdateEvent, 'form' | 'path' | 'op'>;

/** `form_update` 이벤트 (2-0.7). `value`가 undefined면 값은 두고 칸 상태만 바꿉니다. */
const update = (
  form: FormUpdateEvent['form'],
  path: string,
  op: FormUpdateEvent['op'],
  extra: UpdateExtra = {},
): SseMessage => ({ event: 'form_update', data: { form, path, op, ...extra } });

const OVERVIEW =
  '전체 순서는 네 단계예요. 1) 구직등록: 고용24에 이력서를 올려요. 2) 온라인 교육: 수급자격 신청자 교육을 약 1시간 들어요. 3) 수급자격 신청: 고용센터 방문 또는 인터넷 사전제출로 신청해요. 4) 실업인정: 4주마다 재취업활동을 기록하고 신청해요.';

type Script = Record<string, (entryChoices: string[]) => SseMessage[]>;

const COMMON: Script = {
  '전체 순서가 궁금해요': (entryChoices) => [
    ...say(OVERVIEW, SOURCE_WORK24, ['PROC-009', 'PROC-010', 'PROC-011']),
    ask('entry.return', '어디부터 이어갈까요?', entryChoices),
  ],
};

const PARK: Script = {
  '고용24에서 불러올게요': () => openImport('career-certificate', CAREER_IMPORT_TEXT),
  '이력서 만들기 시작할게요': () => [
    ask(
      'resume.career_new',
      '가장 최근에 일하신 곳부터 알려 주세요. 경력증명서가 있으면 사진으로 올려 주세요.',
      ['사진 올릴게요', '고용24에서 불러올게요', '말로 할게요'],
    ),
  ],
  '사진부터 올릴게요': () => [
    ...say('좋아요. 경력증명서나 자격증 사진을 올려 주시면 읽어서 이력서 칸에 넣어 드릴게요.'),
    ask(
      'resume.upload_hint',
      '사진 올리기는 이력서 단계에서 열려요. 지금은 말로 알려 주셔도 돼요.',
      ['말로 할게요', '전체 순서가 궁금해요'],
    ),
  ],
  '말로 할게요': () => [
    ask('resume.career_new', '가장 최근에 일하신 회사 이름과 다니신 기간을 말씀해 주세요.', []),
  ],
  '네, 맞아요': () => [
    update('resume', 'competencies.careers.career_001.main_duties', 'set', {
      value: '프레스 라인 운영, 반장 업무, 신입 안전교육(2025-03~)',
      status: 'confirmed',
      source: 'conversation',
      completeness: { done: 1, total: 5 },
    }),
    update('resume', 'next_question', 'set', { value: 'resume.license' }),
    ask('resume.license', '가지고 계신 자격증이나 면허가 있으세요?', [
      '있어요',
      '없어요',
      '사진 올릴게요',
    ]),
  ],
  없어요: () => [
    update('resume', 'competencies.certifications', 'set', {
      value: [],
      status: 'not_applicable',
      source: 'conversation',
      completeness: { done: 2, total: 5 },
    }),
    update('resume', 'next_question', 'set', { value: 'resume.education_level' }),
    ask('resume.education_level', '마지막으로 다니신 학교는 어디까지세요?', [
      '고등학교 졸업',
      '대학교 졸업',
      '말로 할게요',
    ]),
  ],
};

/** 박진수가 경력을 말로 알려 줄 때 (시안 2-1-1): 서류 없이 대화 값 + '작년 3월' 상대 날짜 확인. */
const parkCareer = (): SseMessage[] => [
  update('resume', 'competencies.careers', 'append', {
    value: {
      item_id: 'career_001',
      company_name: 'OO산업',
      start_date: '2004-03',
      end_date: '2026-09',
      position: '반장',
      employment_status: null,
      occupation: { code: null, name: '생산직(프레스)', status: 'needs_confirmation' },
      main_duties: null,
      monthly_salary: null,
      additional_details: null,
    },
  }),
  update('resume', 'competencies.careers.career_001.company_name', 'set', {
    value: 'OO산업',
    status: 'confirmed',
    source: 'conversation',
    evidence: { kind: 'utterance', date: '2026-10-12', quote: 'OO산업에서' },
  }),
  update('resume', 'competencies.careers.career_001.end_date', 'set', {
    value: '2026-09',
    status: 'confirmed',
    source: 'conversation',
    evidence: {
      kind: 'utterance',
      date: '2026-10-12',
      quote: '그만둘 때까지',
      note: '이직일 2026-09',
    },
  }),
  update('resume', 'competencies.careers.career_001.position', 'set', {
    value: '반장',
    status: 'confirmed',
    source: 'conversation',
  }),
  update('resume', 'competencies.careers.career_001.employment_status', 'set', {
    value: '퇴직',
    status: 'confirmed',
    source: 'computed',
  }),
  update('resume', 'competencies.careers.career_001.main_duties', 'set', {
    value: '프레스 라인 운영, 반장 업무, 신입 안전교육(2025-03~)',
    status: 'extracted',
    source: 'conversation',
    transformed: true,
    evidence: {
      kind: 'utterance',
      date: '2026-10-12',
      quote: '작년 3월부터는 신입 안전교육도',
      note: "'작년 3월' → 2025-03 (기준일 2026-10-12)",
    },
    completeness: { done: 0, total: 5 },
  }),
  update('resume', 'next_question', 'set', { value: 'resume.value_confirm' }),
  ...say('OO산업 2004.03 ~ 2026.09 근무, 직급 반장으로 적었어요.'),
  ask('resume.value_confirm', "'작년 3월'은 2025년 3월로 적을게요. 맞으면 '네'라고 말해 주세요.", [
    '네, 맞아요',
    '아니요, 다시 말할게요',
  ]),
];

const CHOI: Script = {
  '고용24에서 불러올게요': () => openImport('career-certificate', CAREER_IMPORT_TEXT),
  '네, 고칠게요': () => [
    ...say('예전 이력서에서 제목·학력·자격면허를 가져왔어요. 경력과 희망조건은 다시 확인할게요.'),
    ask('resume.career_since_old', '2019년 이후로 일하신 곳이 있나요?', ['네, 있어요', '없어요']),
  ],
  '새로 쓸래요': () => [
    ask(
      'resume.career_new',
      '알겠어요. 가장 최근에 일하신 곳부터 알려 주세요. 경력증명서가 있으면 사진으로 올려 주세요.',
      ['사진 올릴게요', '고용24에서 불러올게요', '말로 할게요'],
    ),
  ],
  '네, 있어요': () => [
    ask('resume.career_new', '회사 이름과 다니신 기간(시작·끝 연월)을 말씀해 주세요.', []),
  ],
  '네, 시설관리요': () => [
    ...['desired_occupations', 'desired_regions', 'desired_salary', 'employment_contract_type'].map(
      (key) =>
        update('resume', `job_preferences.${key}`, 'set', {
          value: CHOI_PREFS[key],
          status: 'confirmed',
          source: 'conversation',
        }),
    ),
    update('resume', 'job_preferences.military_alternative', 'set', {
      value: '해당 없음',
      status: 'confirmed',
      source: 'conversation',
      completeness: { done: 5, total: 5 },
    }),
    update('resume', 'can_save', 'set', { value: true }),
    update('resume', 'next_question', 'set', { value: 'resume.save_ready' }),
    ...say('희망조건을 2019년 값 그대로 확정했어요. 꼭 묻는 5개가 다 채워졌어요.'),
    ask(
      'resume.save_ready',
      "이력서를 다 채웠어요. 오른쪽에서 보시고, 맞으면 '확인하고 이력서 최신화'를 눌러 주세요.",
      ['확인하고 저장할게요', '고칠 게 있어요'],
    ),
  ],
  '확인하고 저장할게요': () => [
    ...say("오른쪽 위 '확인하고 이력서 최신화' 버튼을 눌러 주시면 저장돼요."),
  ],
};

const CHOI_PREFS: Record<string, unknown> = {
  desired_occupations: [{ code: '1431', name: '시설관리', status: 'confirmed' }],
  desired_regions: ['서울 노원구'],
  desired_salary: { amount: 220, unit: 'monthly', negotiable: false },
  employment_contract_type: '기간의 정함이 없는 근로계약',
};

/** 최영수가 2019년 이후 경력을 말할 때 (시안 2-1-2): 경력 2건째 추가 후 희망조건 확인으로 이어짐. */
const choiCareer = (): SseMessage[] => [
  update('resume', 'competencies.careers', 'append', {
    value: {
      item_id: 'career_002',
      company_name: 'OO빌딩',
      start_date: '2022-07',
      end_date: '2026-09',
      position: '시설관리 반장',
      employment_status: '퇴직',
      occupation: { code: null, name: '시설관리', status: 'needs_confirmation' },
      main_duties: '빌딩 전기·소방 설비 점검, 야간 당직',
      monthly_salary: null,
      additional_details: null,
    },
  }),
  ...['company_name', 'start_date', 'end_date', 'position', 'main_duties'].map((key) =>
    update('resume', `competencies.careers.career_002.${key}`, 'set', {
      value: undefined,
      status: 'confirmed',
      source: 'conversation',
      evidence: { kind: 'utterance', date: '2026-10-12', quote: '2022년 7월부터 OO빌딩에서' },
    }),
  ),
  update('resume', 'competencies.careers.career_002.employment_status', 'set', {
    value: '퇴직',
    status: 'confirmed',
    source: 'computed',
  }),
  update('resume', 'competencies.careers', 'set', {
    status: 'confirmed',
    source: 'conversation',
    completeness: { done: 4, total: 5 },
  }),
  update('resume', 'next_question', 'set', { value: 'resume.wish_job' }),
  ...say('OO빌딩 2022.07 ~ 2026.09, 시설관리 반장으로 더했어요. 이제 경력은 2건이에요.'),
  ask('resume.wish_job', '희망조건은 2019년 값이에요. 시설관리 일을 계속 찾으실까요?', [
    '네, 시설관리요',
    '다른 일이요',
  ]),
];

const SOURCE_FORM = '고용24 실업급여(상용직) · 취업드림수첩 2025';
const ANSWERED = '2026-12-16';
const SELF_ANSWER = {
  status: 'confirmed',
  source: 'self_answer',
  evidence: { kind: 'utterance', date: ANSWERED },
} as const;

/** 본인 답변 칸 하나를 채웁니다 (2-3.3: 기본값 없이 사용자가 답한 값만). */
const answer = (path: string, value: unknown) =>
  update('recognition', path, 'set', { value, ...SELF_ANSWER });

const checklist = (done: { self_answers?: boolean; next_activity?: boolean }) =>
  update('recognition', 'checklist', 'set', {
    value: [
      { key: 'self_answers', done: done.self_answers ?? false, blocking: true },
      { key: 'job_search_fields', done: true, blocking: true },
      { key: 'notification', done: true, blocking: true },
      { key: 'next_activity', done: done.next_activity ?? false, blocking: true },
      { key: 'unemployment_credit', done: true, blocking: false },
      { key: 'requirement_met', done: true, blocking: false },
      { key: 'evidence_ok', done: true, blocking: false },
    ],
  });

/** 패널 B → C (2-2.9 → 2-3): 서버가 시작 패널을 C로 바꾸고 본인 답변 질문부터 합니다 (시안 2-3-1). */
const openForm = (): SseMessage[] => [
  update('procedure', 'entry.panel', 'set', { value: 'C' }),
  update('procedure', 'entry.title', 'set', { value: '실업인정 신청서 검토' }),
  ...say(
    '4차 신청서를 고용24 순서대로 정리했어요. 구직활동 2건은 고용24 불러오기라 칸이 다 차 있고, 같은 날 뺀 OO상사는 참고로만 보여 드려요. 이제 본인이 꼭 답해야 하는 질문을 할게요.',
  ),
  ...say(
    '11월 25일(수)부터 12월 22일(화) 사이에 하루라도 일하거나 돈을 번 적이 있나요? 아르바이트, 일용직, 수당 받는 회의 참석, 블로그·유튜브 수익도 포함이에요.',
    SOURCE_FORM,
    ['DUE-002', 'DUE-102'],
  ),
  ask('form.work', '답을 골라 주세요. 기본값은 없어요.', ['없어요', '있어요', '잘 모르겠어요']),
];

const consentAnswer = (value: 'agree' | 'disagree' | 'decide_on_work24') => (): SseMessage[] => [
  answer('personal_information_consent', { value, answered_on: ANSWERED }),
  update('recognition', 'can_submit', 'set', { value: true }),
  ...say(
    "제출 전 확인을 다 마쳤어요. 4차는 고용센터에 직접 가는 출석 회차라 인터넷으로 내지 않아요. 오른쪽에서 신분증과 수급자격증을 챙겼는지 체크하고 '출석 준비 확인 (모의)'를 눌러 주세요. 신청은 본인이 직접 해요.",
    SOURCE_FORM,
    ['ACT-040', 'PROC-076', 'DUE-001'],
  ),
];

const ASK_EMPLOYMENT = ask(
  'form.employment',
  '같은 기간에 취업했거나 취업이 정해졌나요? 개인 사업을 시작한 것도 포함이에요.',
  ['아니요, 안 했어요', '네, 취업했어요'],
);

/** 근로 있음 상세 (2-3.3): 고용24 칸대로 일한 날 → 총 근로시간 → 소득수령(예정)일 → 금액을 하나씩 묻습니다. */
const workDetail = (path: string, value: unknown) =>
  answer(`work_and_employment.work_details.${path}`, value);

/** 작성을 멈추는 답 (2-3.3 질문 2·3): 패널 C를 잠그고 고용센터 문의를 안내합니다. */
const lockForm = (
  path: string,
  reason: 'employment' | 'industrial_accident',
  text: string,
): SseMessage[] => [
  answer(path, true),
  update('recognition', 'locked_reason', 'set', { value: reason }),
  ...say(text, SOURCE_FORM, reason === 'employment' ? ['PROC-079'] : ['ACT-086']),
];

const LEE_WORK: Script = {
  있어요: () => [
    answer('work_and_employment.has_work_or_service', true),
    update('recognition', 'work_and_employment.work_details', 'set', {
      value: { work_dates: null, total_hours: null, income_date: null, income_amount: null },
    }),
    ...say('일한 날은 신청서에 꼭 적어야 해요. 고용24 칸대로 하나씩 여쭤볼게요.'),
    ask('form.work_dates', '언제 일하셨어요? 일한 날을 모두 말해 주세요.', ['12월 5일 하루요']),
  ],
  '12월 5일 하루요': () => [
    workDetail('work_dates', '2026-12-05 (1일)'),
    ask('form.work_hours', '그날 모두 몇 시간 일하셨어요?', ['8시간이요']),
  ],
  '8시간이요': () => [
    workDetail('total_hours', 8),
    ask('form.income_date', '돈은 언제 받으셨어요? 아직이면 받기로 한 날을 알려 주세요.', [
      '12월 10일에 받았어요',
    ]),
  ],
  '12월 10일에 받았어요': () => [
    workDetail('income_date', '2026-12-10'),
    ask('form.income_amount', '얼마를 받으셨어요?', ['10만 원이요']),
  ],
  '10만 원이요': () => [
    workDetail('income_amount', 100000),
    update('recognition', 'work_and_employment.answered_on', 'set', { value: ANSWERED }),
    ...say(
      '12월 5일 8시간, 12월 10일에 10만 원으로 적었어요. 일한 시간이 길면 취업으로 볼 수도 있어요. 고용센터에 확인해 주세요.',
      SOURCE_FORM,
      ['DUE-045', 'DUE-102'],
    ),
    ASK_EMPLOYMENT,
  ],
  '잘 모르겠어요': () => [
    ...say(
      '하루라도 아르바이트나 일용직을 했거나, 수당을 받고 회의에 나갔거나, 블로그·유튜브로 수익이 났다면 모두 신고해야 해요. 금액이나 이름과 관계없어요.',
      SOURCE_FORM,
      ['DUE-102'],
    ),
    ask('form.work_retry', '이 중에 해당하는 게 있었나요?', [
      '없어요',
      '있어요',
      '그래도 모르겠어요',
    ]),
  ],
  '그래도 모르겠어요': () => [
    update('recognition', 'work_and_employment.has_work_or_service', 'set', {
      value: null,
      status: 'conflict',
      source: 'self_answer',
      evidence: { kind: 'utterance', date: ANSWERED, note: '본인이 잘 모르겠다고 답함' },
    }),
    ...say(
      '그럼 이 칸은 확인 필요로 둘게요. 제출 전에 관할 고용센터에 꼭 확인해 주세요. 이 칸이 정해지기 전에는 제출할 수 없어요.',
      SOURCE_FORM,
      ['DUE-002'],
    ),
    ASK_EMPLOYMENT,
  ],
  '네, 취업했어요': () =>
    lockForm(
      'work_and_employment.has_employment',
      'employment',
      '취업을 축하드려요. 실업인정일 전에 관할 고용센터에 먼저 문의해 주세요. 신청서와 근로계약서(재직증명서)는 취업일로부터 2개월 안에 내야 해요. 고용24 `취업사실 신고` 메뉴에서 신고할 수 있어요.',
    ),
  '네, 받고 있어요': () =>
    lockForm(
      'work_and_employment.has_industrial_accident_benefit_right',
      'industrial_accident',
      '이 경우는 인터넷으로 실업인정을 신청할 수 없어요. 출석일 전에 관할 고용센터에 문의해 주세요.',
    ),
};

/** 신청서 본인 답변 → 출석 준비 확인 → 다음 실업인정일 (시안 2-3-1 → 2-3-2 → 5차 첫 화면). */
const LEE_FORM: Script = {
  ...LEE_WORK,
  [OPEN_FORM_MESSAGE]: () => openForm(),
  '신청서 볼게요': () => openForm(),
  '네, 볼게요': () => openForm(),
  없어요: () => [
    answer('work_and_employment.has_work_or_service', false),
    ask(
      'form.employment',
      '같은 기간에 취업했거나 취업이 정해졌나요? 개인 사업을 시작한 것도 포함이에요.',
      ['아니요, 안 했어요', '네, 취업했어요'],
    ),
  ],
  '아니요, 안 했어요': () => [
    answer('work_and_employment.has_employment', false),
    ask('form.accident', '산재 휴업급여를 받고 있거나 받을 권리가 있나요?', [
      '아니요, 해당 없어요',
      '네, 받고 있어요',
    ]),
  ],
  '아니요, 해당 없어요': () => [
    answer('work_and_employment.has_industrial_accident_benefit_right', false),
    update('recognition', 'work_and_employment.answered_on', 'set', { value: ANSWERED }),
    checklist({ self_answers: true }),
    ask(
      'form.notification',
      "구직급여 지급 결정 통지는 지난번처럼 '휴대전화 문자메시지'로 둘까요?",
      ['그대로 둘게요', '바꿀게요'],
    ),
  ],
  '그대로 둘게요': () => [
    answer('notification_and_plan.payment_notification_method', '휴대전화 문자메시지'),
    ...say(
      '5차는 4주에 활동 2건, 그중 구직활동 1건이 꼭 있어야 해요. 다음 출석일까지 할 활동은 고용24 선택지에서 하나를 골라 적어요.',
      SOURCE_2026_NOTICE,
      ['ACT-027', 'ACT-028'],
    ),
    ask('form.next_activity', "'구직활동'에 메모 '입사지원'으로 적을까요?", [
      '네, 그렇게 할게요',
      '다른 활동이요',
    ]),
  ],
  '네, 그렇게 할게요': () => [
    answer('notification_and_plan.next_activity', {
      value: '구직활동',
      memo: '입사지원',
      answered_on: ANSWERED,
    }),
    checklist({ self_answers: true, next_activity: true }),
    ask(
      'form.consent',
      '실업급여 제도 안내 연락 같은 개인정보 이용 동의는 선택이에요. 어떻게 할까요?',
      ['동의해요', '안 할래요', '고용24에서 고를게요'],
    ),
  ],
  동의해요: consentAnswer('agree'),
  '안 할래요': consentAnswer('disagree'),
  '고용24에서 고를게요': consentAnswer('decide_on_work24'),
  [CONFIRMED_MESSAGE.attend]: () => [
    ...say(
      '12월 22일(화)에 고용센터에 다녀오시면 다음 실업인정일을 알려 주세요. 다음 회차 준비를 이어서 도와드릴게요.',
    ),
    ask('procedure.next_date', '다음 실업인정일을 안내받으면 말씀해 주세요.', [
      '다음은 1월 19일이래요',
    ]),
  ],
};

const LEE_PERSONA = MOCK_PERSONAS.find((persona) => persona.persona_id === 'lee');

/**
 * "다음은 1월 19일이래요" (2-3.7 · 평가 form-005): 백엔드 `advance_round` 결과를 흉내 내 세션의
 * 상태·파생값·진입 결과를 5차로 바꿉니다. 시연 계정은 기준일도 이번 인정일(12.22)로 옮깁니다.
 */
const advanceRound = (): SseMessage[] => {
  if (!LEE_PERSONA) return [];
  return [
    ...tool('update_procedure_state'),
    update('procedure', 'state', 'set', {
      value: {
        ...LEE_PERSONA.state,
        completed_rounds: 4,
        last_recognition_date: '2026-12-22',
        next_recognition_date: '2027-01-19',
        demo_today: '2026-12-22',
      },
    }),
    update('procedure', 'derived', 'set', {
      value: {
        ...LEE_PERSONA.derived,
        current_round: 5,
        d_day: 28,
        period: { start: '2026-12-23', end: '2027-01-19' },
        is_attendance_round: false,
      },
    }),
    update('procedure', 'entry.panel', 'set', { value: 'B' }),
    update('procedure', 'entry.title', 'set', { value: '이번 회차 할 일' }),
    update('procedure', 'entry.next_step_text', 'set', {
      value: '다음 기한 : 5차 실업인정일 1.19(화)',
    }),
    ...say(
      '이정호님, 4차 실업인정까지 받으셨네요. 이제 5차 실업인정 준비를 시작해 볼까요? 1월 19일(화)까지 28일 남았어요.',
    ),
    ...say(
      '5차는 4주에 활동 2건, 그중 구직활동 1건이 꼭 있어야 해요. 지금 기록된 활동은 0건이라 2건이 더 필요해요. 5차는 인터넷으로 신청할 수 있어요.',
      SOURCE_2026_NOTICE,
      ['ACT-027', 'ACT-028', 'DUE-044', 'DUE-090'],
    ),
    ask('entry.choices', '무엇부터 할까요?', ['부족한 활동 추천해 주세요', '새 활동 기록할게요']),
  ];
};

const LEE: Script = {
  '부족한 활동 추천해 주세요': () => [
    ...tool('check_activity_rules'),
    update('activities', 'recommendations_open', 'set', { value: true }),
    ...say(
      '지금 인정되는 활동은 1건이고 구직활동은 이미 1건 있어요. 12월 8일이 아닌 다른 날 활동이 1건 더 필요해요. 증빙이 쉬운 순서로 추천할게요. 1) 고용24로 희망 직종 공고에 입사지원(증빙 불필요) 2) 온라인 취업특강 1과정을 끝까지(증빙 불필요) 3) 잡힌 면접이 있으면 면접(면접확인서 + 명함). 인정일 전날 12월 21일(월)까지 하시길 권해요.',
      SOURCE_2026_NOTICE,
      ['ACT-001', 'ACT-132', 'ACT-043', 'ACT-117', 'ACT-002', 'ACT-137'],
    ),
    ask('round.recommend', '어떤 활동으로 할까요?', [
      '고용24 입사지원 할게요',
      '온라인 취업특강 들을게요',
      '새 활동 기록할게요',
    ]),
  ],
  '새 활동 기록할게요': () => [
    ask('activity.date', '언제 하셨어요? 고용24로 지원하셨으면 불러올 수도 있어요.', [
      '오늘',
      '어제',
      '고용24에서 불러올게요',
    ]),
  ],
  '고용24에서 불러올게요': () =>
    openImport('work24-activities', '고용24 입사지원 내역에서 이번 회차 활동을 골라 주세요.'),
  오늘: () => [ask('activity.category', '어떤 활동이었어요?', ['입사지원', '면접', '다른 활동'])],
  입사지원: () => [ask('activity.org_name', '어느 회사(기관)였어요?', [])],
  '고용24 입사지원 할게요': () => [
    ...say(
      '고용24 채용정보에서 일반 사무 공고를 골라 지원해 주세요. 지원하시면 여기서 "방금 고용24로 OO물산에 지원했어요"처럼 말씀해 주세요.',
    ),
  ],
  ...LEE_FORM,
  '신청서 미리 볼래요': () => [
    ...say('아직 1건이 부족해요. 그래도 신청서를 볼까요?'),
    ask('round.open_form', '신청서를 열면 본인 답변 질문부터 시작해요.', [
      '네, 볼게요',
      '활동 먼저 채울게요',
    ]),
  ],
};

const RECORD_PATTERN = /고용24.*지원|지원.*고용24/;
const NEXT_DATE_PATTERN = /1월\s*19일/;
const PARK_CAREER_PATTERN = /OO산업|프레스|반장/;
const CHOI_CAREER_PATTERN = /OO빌딩|2022/;

/**
 * 이정호가 "방금 고용24로 OO물산에 지원했어요"라고 말할 때 (시안 2-2-2): 활동 추가 → `check_round` 다시 계산 →
 * 필요 활동 카드가 충족으로 바뀜. 숫자는 백엔드 계산 결과를 흉내 낸 값입니다.
 */
const recordActivity = (): SseMessage[] => [
  update('activities', 'activities', 'append', {
    value: {
      item_id: 'a3',
      round: 4,
      date: '2026-12-16',
      category: '입사지원',
      kind: 'job_search',
      route: 'work24',
      org_name: 'OO물산',
      job_title: '사무보조',
      evidence: { required: [], attached: [] },
      source: 'work24_import',
      status: 'counted',
      rule_refs: ['ACT-001', 'ACT-132'],
    },
    evidence: { kind: 'utterance', date: '2026-12-16', quote: '고용24로 OO물산' },
  }),
  ...tool('check_activity_rules'),
  ...(
    [
      ['counted', 2],
      ['counted_job_search', 2],
      ['shortfall', 0],
      ['status', 'satisfied'],
      ['recommendations_open', false],
    ] as const
  ).map(([path, value]) => update('activities', path, 'set', { value })),
  ...say(
    '12월 16일 OO물산 고용24 입사지원을 기록했어요. 고용24 경로는 신청할 때 불러오기로 확인하니 증빙이 필요 없어요. 이제 인정 2건(구직활동 2건)으로 이번 회차 필요 활동을 채웠어요.',
    SOURCE_2026_NOTICE,
    ['ACT-132', 'ACT-025', 'ACT-026'],
  ),
  ask('round.satisfied', '다음으로 무엇을 할까요?', ['신청서 볼게요', '활동 더 기록할게요']),
];

const BY_PERSONA: Record<string, Script> = { park: PARK, choi: CHOI, lee: LEE };

const DOC = { status: 'extracted', source: 'document' } as const;
const CERT_DOC_EVIDENCE = { kind: 'document', note: '경력증명서 사진' };

/** 박진수가 경력증명서 사진을 올렸을 때 (시안 2-1-1 ①): 주민등록번호 가림 안내 + 서류 값 + 다음 질문. */
const parkDocument = (): SseMessage[] => [
  ...tool('parse_file'),
  update('resume', 'competencies.careers', 'append', {
    value: {
      item_id: 'career_001',
      company_name: 'OO산업',
      start_date: '2004-03',
      end_date: '2026-09',
      position: null,
      employment_status: '퇴직',
      occupation: { code: null, name: '생산직(프레스)', status: 'needs_confirmation' },
      main_duties: null,
      monthly_salary: null,
      additional_details: null,
    },
  }),
  ...['company_name', 'start_date', 'end_date'].map((key) =>
    update('resume', `competencies.careers.career_001.${key}`, 'set', {
      ...DOC,
      evidence: CERT_DOC_EVIDENCE,
    }),
  ),
  update('resume', 'competencies.careers.career_001.employment_status', 'set', {
    status: 'confirmed',
    source: 'computed',
  }),
  update('resume', 'competencies.certifications', 'append', {
    value: {
      item_id: 'cert_001',
      certificate_name: '지게차운전기능사',
      issuing_organization: null,
      acquired_date: null,
    },
  }),
  update('resume', 'competencies.certifications.cert_001.certificate_name', 'set', {
    ...DOC,
    evidence: { kind: 'document', note: '자격증 사진' },
    completeness: { done: 1, total: 5 },
  }),
  update('resume', 'next_question', 'set', { value: 'resume.career_duties' }),
  ...say(
    '주민등록번호가 보여 가리고 읽었어요(저장하지 않아요). OO산업 2004.03 ~ 2026.09 근무와 지게차운전기능사 자격을 확인했어요.',
  ),
  ask('resume.career_duties', 'OO산업에서 주로 어떤 일을 하셨어요?', []),
];

/**
 * 이정호가 지원 완료 캡처를 올렸을 때 (2-2.5: 캡처에서 활동을 뽑고, 경로별 증빙을 정함).
 * 날짜·회사·경로를 읽어 활동 1건을 더하고 다시 계산한 결과를 흉내 냅니다.
 */
const leeCapture = (): SseMessage[] => [
  ...tool('parse_file'),
  update('activities', 'activities', 'append', {
    value: {
      item_id: 'a4',
      round: 4,
      date: '2026-12-15',
      category: '입사지원',
      kind: 'job_search',
      route: 'company_site',
      org_name: 'OO기획',
      job_title: null,
      evidence: { required: ['채용공고', '지원 완료 화면 캡처'], attached: ['지원완료_캡처.png'] },
      source: 'document',
      status: 'counted',
      rule_refs: ['ACT-001', 'ACT-136'],
    },
  }),
  ...tool('check_activity_rules'),
  ...(
    [
      ['counted', 2],
      ['counted_job_search', 2],
      ['shortfall', 0],
      ['status', 'satisfied'],
    ] as const
  ).map(([path, value]) => update('activities', path, 'set', { value })),
  ...say(
    '지원 완료 화면에서 12월 15일 OO기획 홈페이지 지원 1건을 읽었어요. 회사 홈페이지 지원은 채용공고와 날짜가 보이는 지원 완료 화면이 증빙이에요. 채용공고도 같이 남겨 두세요. 이제 인정 2건으로 이번 회차 필요 활동을 채웠어요.',
    SOURCE_2026_NOTICE,
    ['ACT-136', 'ACT-025', 'ACT-026'],
  ),
  ask('round.satisfied', '다음으로 무엇을 할까요?', ['신청서 볼게요', '활동 더 기록할게요']),
];

const documentFallback = (entryChoices: string[]): SseMessage[] => [
  ...say(
    '이 사진에서는 이력서에 쓸 내용을 못 찾았어요. 경력증명서·자격증·예전 이력서 사진이면 다시 올려 주세요.',
  ),
  ask('resume.doc_retry', '어떻게 할까요?', [
    '다시 찍을게요',
    '말로 할게요',
    ...entryChoices.slice(0, 1),
  ]),
];

const W24 = { status: 'extracted', source: 'work24_import' } as const;

/**
 * 불러오기에서 고른 항목을 넣습니다 (2-1.5 · 2-2.5). 고용24처럼 경력은 회사명·재직기간만 들어오고
 * 직급/직책·주요 직무는 이어서 묻습니다.
 */
const importEvents = (personaId: string, importIds: string[]): SseMessage[] => {
  if (personaId === 'lee') {
    return importIds.includes('wa_003') ? recordActivity() : [];
  }
  const events: SseMessage[] = [];
  const names: string[] = [];
  const careers: Record<string, [string, string, string, string]> = {
    cc_career_001: ['career_001', 'OO산업', '2004-03', '2026-09'],
    cc_career_002: ['career_002', 'OO빌딩', '2022-07', '2026-09'],
  };
  const firstCareer = importIds.map((id) => careers[id]).find(Boolean);
  for (const id of importIds) {
    const career = careers[id];
    if (career) {
      const [itemId, company, start, end] = career;
      events.push(
        update('resume', 'competencies.careers', 'append', {
          value: {
            item_id: itemId,
            company_name: company,
            start_date: start,
            end_date: end,
            position: null,
            employment_status: '퇴직',
            occupation: null,
            main_duties: null,
            monthly_salary: null,
            additional_details: null,
          },
        }),
        ...['company_name', 'start_date', 'end_date'].map((key) =>
          update('resume', `competencies.careers.${itemId}.${key}`, 'set', W24),
        ),
        update('resume', `competencies.careers.${itemId}.employment_status`, 'set', {
          status: 'confirmed',
          source: 'computed',
        }),
      );
      names.push(`${company} ${start.replace('-', '.')} ~ ${end.replace('-', '.')} 근무`);
    }
    if (id === 'cc_license_001' && personaId === 'park') {
      events.push(
        update('resume', 'competencies.certifications', 'append', {
          value: {
            item_id: 'cert_001',
            certificate_name: '지게차운전기능사',
            issuing_organization: '한국산업인력공단',
            acquired_date: '2011-05-20',
          },
        }),
        update('resume', 'competencies.certifications.cert_001.certificate_name', 'set', {
          ...W24,
          completeness: { done: 1, total: 5 },
        }),
      );
      names.push('지게차운전기능사 자격');
    }
    if (id === 'cc_training_001') {
      events.push(
        update('resume', 'competencies.vocational_training', 'set', {
          value: [{ item_id: 'training_001', name: '용접 기초 과정', period: '2009.03 ~ 2009.06' }],
          ...W24,
        }),
      );
      names.push('직업훈련 이수이력(용접 기초 과정)');
    }
  }
  events.push(...say(`고용24에서 고르신 ${names.join(', ')}을 넣었어요.`));
  if (firstCareer) {
    const [itemId, company] = firstCareer;
    events.push(
      update('resume', 'next_question', 'set', { value: 'resume.career_position' }),
      ask(
        `resume.career_position.${itemId}`,
        `${company}에서 직급이나 직책이 있으셨어요? 없으면 '없음'으로 적어요.`,
        ['말로 할게요', '없었어요'],
      ),
    );
  }
  return events;
};

export const buildMockChatEvents = (
  personaId: string,
  message: string,
  entryChoices: string[],
  fileIds?: string[],
  importIds?: string[],
): SseMessage[] => {
  if (importIds?.length) return importEvents(personaId, importIds);
  if (fileIds?.length) {
    if (personaId === 'park') return parkDocument();
    return personaId === 'lee' ? leeCapture() : documentFallback(entryChoices);
  }
  const key = message.trim();
  const script = BY_PERSONA[personaId]?.[key] ?? COMMON[key];
  if (script) return script(entryChoices);
  if (personaId === 'lee' && RECORD_PATTERN.test(key)) return recordActivity();
  if (personaId === 'lee' && NEXT_DATE_PATTERN.test(key)) return advanceRound();
  if (personaId === 'park' && PARK_CAREER_PATTERN.test(key)) return parkCareer();
  if (personaId === 'choi' && CHOI_CAREER_PATTERN.test(key)) return choiCareer();

  return [
    ...say(
      '말씀 감사해요. 이 부분은 시연 대화가 아직 준비되지 않았어요. 아래 선택지로 이어가 주세요.',
    ),
    ask('mock.fallback', '어디부터 이어갈까요?', entryChoices),
  ];
};

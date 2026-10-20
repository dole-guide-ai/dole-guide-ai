import { OPEN_FORM_MESSAGE } from '@/features/procedure/activityLabels';

import type { FormUpdateEvent, SseMessage } from '@/types/chat.types';

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

const ask = (question_id: string, text: string, choices: string[]): SseMessage => ({
  event: 'ask_user',
  data: { question_id, text, choices },
});

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
  '새 활동 기록할게요': () => [ask('activity.date', '언제 하셨어요?', ['오늘', '어제', '다른 날'])],
  오늘: () => [ask('activity.category', '어떤 활동이었어요?', ['입사지원', '면접', '다른 활동'])],
  입사지원: () => [ask('activity.org_name', '어느 회사(기관)였어요?', [])],
  '고용24 입사지원 할게요': () => [
    ...say(
      '고용24 채용정보에서 일반 사무 공고를 골라 지원해 주세요. 지원하시면 여기서 "방금 고용24로 OO물산에 지원했어요"처럼 말씀해 주세요.',
    ),
  ],
  [OPEN_FORM_MESSAGE]: () => [
    ...say(
      '이번 회차 활동으로 실업인정 신청서를 고용24 순서대로 정리할게요. 신청서 화면(패널 C)은 다음 단계에서 열려요.',
    ),
  ],
  '신청서 미리 볼래요': () => [
    ...say('아직 1건이 부족해요. 그래도 신청서를 볼까요?'),
    ask('round.open_form', '신청서를 열면 본인 답변 질문부터 시작해요.', [
      '네, 볼게요',
      '활동 먼저 채울게요',
    ]),
  ],
};

const RECORD_PATTERN = /고용24.*지원|지원.*고용24/;
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
  ask('round.satisfied', '다음으로 무엇을 할까요?', ['신청서 미리 볼래요', '활동 더 기록할게요']),
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

export const buildMockChatEvents = (
  personaId: string,
  message: string,
  entryChoices: string[],
  fileIds?: string[],
): SseMessage[] => {
  if (fileIds?.length) {
    return personaId === 'park' ? parkDocument() : documentFallback(entryChoices);
  }
  const key = message.trim();
  const script = BY_PERSONA[personaId]?.[key] ?? COMMON[key];
  if (script) return script(entryChoices);
  if (personaId === 'lee' && RECORD_PATTERN.test(key)) return recordActivity();
  if (personaId === 'park' && PARK_CAREER_PATTERN.test(key)) return parkCareer();
  if (personaId === 'choi' && CHOI_CAREER_PATTERN.test(key)) return choiCareer();

  return [
    ...say(
      '말씀 감사해요. 이 부분은 시연 대화가 아직 준비되지 않았어요. 아래 선택지로 이어가 주세요.',
    ),
    ask('mock.fallback', '어디부터 이어갈까요?', entryChoices),
  ];
};

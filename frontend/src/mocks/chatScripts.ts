import type { SseMessage } from '@/types/chat.types';

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
};

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
};

const LEE: Script = {
  '부족한 활동 추천해 주세요': () => [
    ...tool('check_activity_rules'),
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
  '신청서 미리 볼래요': () => [
    ...say('아직 1건이 부족해요. 그래도 신청서를 볼까요?'),
    ask('round.open_form', '신청서를 열면 본인 답변 질문부터 시작해요.', [
      '네, 볼게요',
      '활동 먼저 채울게요',
    ]),
  ],
};

const RECORD_PATTERN = /고용24.*지원|지원.*고용24/;

const recordActivity = (): SseMessage[] => [
  {
    event: 'form_update',
    data: {
      form: 'activities',
      path: 'items',
      op: 'append',
      value: {
        item_id: 'a3',
        date: '2026-12-16',
        category: '입사지원',
        org_name: 'OO물산',
        route: 'work24',
        kind: 'job_search',
        status: 'counted',
      },
      status: 'extracted',
      source: 'work24_import',
      evidence: { kind: 'utterance', date: '2026-12-16', quote: '고용24로 OO물산' },
    },
  },
  ...tool('check_activity_rules'),
  ...say(
    '12월 16일 OO물산 고용24 입사지원을 기록했어요. 고용24 경로는 신청할 때 불러오기로 확인하니 증빙이 필요 없어요. 이제 인정 2건(구직활동 2건)으로 이번 회차 필요 활동을 채웠어요.',
    SOURCE_2026_NOTICE,
    ['ACT-132', 'ACT-025', 'ACT-026'],
  ),
  ask('round.satisfied', '다음으로 무엇을 할까요?', ['신청서 미리 볼래요', '활동 더 기록할게요']),
];

const BY_PERSONA: Record<string, Script> = { park: PARK, choi: CHOI, lee: LEE };

export const buildMockChatEvents = (
  personaId: string,
  message: string,
  entryChoices: string[],
): SseMessage[] => {
  const key = message.trim();
  const script = BY_PERSONA[personaId]?.[key] ?? COMMON[key];
  if (script) return script(entryChoices);
  if (personaId === 'lee' && RECORD_PATTERN.test(key)) return recordActivity();

  return [
    ...say(
      '말씀 감사해요. 이 부분은 시연 대화가 아직 준비되지 않았어요. 아래 선택지로 이어가 주세요.',
    ),
    ask('mock.fallback', '어디부터 이어갈까요?', entryChoices),
  ];
};

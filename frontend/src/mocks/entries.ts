import { citeOf } from '@/lib/sources';
import type { EntryResult } from '@/types/demo.types';

/**
 * 계정별 진입 결과 스냅샷 (상세기획 1.6 분기 표 · 1.7 템플릿 · 1.11 예시).
 * 분기 계산은 백엔드 순수 함수가 하고, 여기는 그 결과만 둡니다.
 */
const SOURCE_WORK24 = citeOf('SRC-001');
const SOURCE_2026_NOTICE = citeOf('SRC-008', 'SRC-016');

export const MOCK_ENTRIES: Record<string, EntryResult> = {
  // E7a: 이력서 없음
  park: {
    branch_id: 'E7a',
    panel: 'A',
    progress: { current: 1, done: [] },
    title: '이력서부터 같이 만들어요',
    next_step_text: '다음 할 일 : 이력서 저장 후 온라인 교육(약 1시간)',
    messages: [
      {
        template_id: 'T-E7a',
        text: '박진수님, 반가워요. 아직 이력서가 없으시군요. 구직등록에 쓸 이력서부터 같이 만들어 볼까요? 경력증명서나 예전 서류가 있으면 파일(사진·문서)로 올려 주시고, 없으면 말로 하셔도 돼요.',
        cite: SOURCE_WORK24,
      },
    ],
    choices: ['이력서 만들기 시작할게요', '사진부터 올릴게요', '전체 순서가 궁금해요'],
    // 첫 안내가 경력증명서·예전 서류를 요청하므로 파일 올리기를 켭니다 (2-0.4 accepts_file).
    accepts_file: true,
    ui: { big_text: false },
    rule_refs: ['PROC-009'],
  },
  // E7b + M1 + M4: 예전 이력서, 이직 당시 67세
  choi: {
    branch_id: 'E7b',
    panel: 'A',
    progress: { current: 1, done: [] },
    title: '이력서부터 같이 만들어요',
    next_step_text: '다음 할 일 : 이력서 최신화 → 온라인 교육 → 고용센터 방문 신청',
    messages: [
      {
        template_id: 'T-E7b',
        text: '최영수님, 반가워요. 2019년에 쓰신 이력서가 있네요. 그 뒤로 일하신 곳만 더하면 최신 이력서가 돼요. 같이 고쳐 볼까요?',
      },
      {
        template_id: 'T-M1',
        text: '참고로 그만두실 때 67세셨으니, 수급자격 신청은 인터넷 사전제출 대신 관할 고용센터에 방문해서 해요. 실업급여를 못 받는다는 뜻은 아니에요.',
        cite: SOURCE_WORK24,
      },
    ],
    choices: ['네, 고칠게요', '새로 쓸래요', '전체 순서가 궁금해요'],
    ui: { big_text: true },
    rule_refs: ['PROC-009', 'PROC-085', 'PROC-048'],
  },
  // E4b + T-S + M3: 3차 완료, 4차 준비 (1.11 예시 그대로)
  lee: {
    branch_id: 'E4b',
    panel: 'B',
    progress: { current: 4, done: [1, 2, 3] },
    title: '이번 회차 할 일',
    next_step_text: '다음 기한 : 4차 실업인정일 12.22(화) · 고용센터 출석',
    messages: [
      {
        template_id: 'T-E4b',
        text: '이정호님, 3차 실업인정까지 받으셨네요. 이제 4차 실업인정 준비를 시작해 볼까요? 12월 22일(화)까지 6일 남았어요.',
      },
      {
        template_id: 'T-S+M3',
        text: '4차는 4주에 활동 2건, 그중 구직활동 1건이 꼭 있어야 해요. 지금 기록된 활동은 2건인데 둘 다 12월 8일이라 1건만 인정돼요. 다른 날 활동이 1건 더 필요해요. 4차는 고용센터에 직접 가는 출석 회차예요.',
        cite: SOURCE_2026_NOTICE,
      },
    ],
    choices: ['부족한 활동 추천해 주세요', '이미 한 활동 기록할게요', '신청서 미리 볼래요'],
    ui: { big_text: false },
    rule_refs: ['ACT-025', 'ACT-026', 'ACT-055', 'ACT-110', 'ACT-040', 'DUE-090'],
  },
};

const EDUCATION_CHOICES = ['교육 다 들었어요', '어디서 들어요?', '꼭 들어야 해요?'];
const WORK24_INPUT_HINT =
  "고용24에 옮겨 적으실 때 참고하세요.\n· 직무능력은 고용24에서 '직무능력 자동 추천'으로 골라 주세요.\n· 희망임금은 금액 앞 선택 상자에서 월급 단위를 고르세요.";

/** 이력서 저장(2-1.6) 뒤 진입 결과: 단계가 온라인 교육(E6)으로 넘어갑니다. */
export const MOCK_AFTER_RESUME_ENTRIES: Record<string, EntryResult> = {
  park: {
    branch_id: 'E6',
    panel: 'E',
    progress: { current: 2, done: [1] },
    title: '온라인 교육을 들어요',
    next_step_text: '다음 할 일 : 온라인 교육 이수 후 수급자격 신청',
    messages: [
      {
        template_id: 'T-SAVE-E7a',
        text: '이력서를 저장해서 구직등록이 끝났어요. 다음은 수급자격 신청자 온라인 교육이에요. 약 1시간이고, 다 들으시면 아래 ‘교육 다 들었어요’를 눌러 알려 주세요.',
        cite: SOURCE_WORK24,
      },
      { template_id: 'T-WORK24-HINT', text: WORK24_INPUT_HINT },
    ],
    choices: EDUCATION_CHOICES,
    ui: { big_text: false },
    rule_refs: ['PROC-009', 'PROC-010'],
  },
  choi: {
    branch_id: 'E6',
    panel: 'E',
    progress: { current: 2, done: [1] },
    title: '온라인 교육을 들어요',
    next_step_text: '다음 할 일 : 온라인 교육 → 고용센터 방문 신청',
    messages: [
      {
        template_id: 'T-SAVE-E7b',
        text: '이력서를 최신화해 저장했어요. 구직등록이 끝났어요. 다음은 온라인 교육이에요. 글씨를 크게 해 두었으니 천천히 들으시고, 다 들으시면 아래 ‘교육 다 들었어요’를 눌러 알려 주세요.',
        cite: SOURCE_WORK24,
      },
      { template_id: 'T-WORK24-HINT', text: WORK24_INPUT_HINT },
    ],
    choices: EDUCATION_CHOICES,
    ui: { big_text: true },
    rule_refs: ['PROC-009', 'PROC-010', 'PROC-048'],
  },
};

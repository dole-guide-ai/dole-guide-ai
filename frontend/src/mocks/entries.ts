import type { EntryResult } from '@/types/demo.types';

/**
 * 계정별 진입 결과 스냅샷 (상세기획 1.6 분기 표 · 1.7 템플릿 · 1.11 예시).
 * 분기 계산은 백엔드 순수 함수가 하고, 여기는 그 결과만 둡니다.
 */
const SOURCE_WORK24 = '고용24 실업급여(상용직)';
const SOURCE_2026_NOTICE = '실업인정 인정기준 안내문(2026.3.1~ 신청자) · 취업드림수첩 2025';

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
        text: '박진수님, 반가워요. 아직 이력서가 없으시군요. 구직등록에 쓸 이력서부터 같이 만들어 볼까요? 경력증명서나 예전 서류가 있으면 사진으로 올려 주시고, 없으면 말로 하셔도 돼요.',
        cite: SOURCE_WORK24,
      },
    ],
    choices: ['이력서 만들기 시작할게요', '사진부터 올릴게요', '전체 순서가 궁금해요'],
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
    choices: ['부족한 활동 추천해 주세요', '새 활동 기록할게요', '신청서 미리 볼래요'],
    ui: { big_text: false },
    rule_refs: ['ACT-025', 'ACT-026', 'ACT-055', 'ACT-110', 'ACT-040', 'DUE-090'],
  },
};

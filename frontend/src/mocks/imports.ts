import type { ImportItem, ImportKind, ImportListRead } from '@/types/imports.types';

/**
 * 고용24 불러오기 모의 목록 (2-1.5 통합경력증명 · 2-2.5 고용24 입사지원 내역). 모두 가상 값입니다.
 * 박진수의 직업훈련 이력은 도현 실측("기억에 없는 무언가 튀어나옴")처럼 본인이 빼고 고를 수 있는 예입니다.
 */
const NOTE_CAREER = '고용24 ‘이력보기’를 흉내 낸 모의 목록이에요. 넣을 것만 골라 주세요.';
const NOTE_WORK24 = '고용24 ‘구직활동 불러오기’를 흉내 낸 모의 목록이에요.';

const PARK: ImportItem[] = [
  {
    import_id: 'cc_career_001',
    category: 'career',
    title: 'OO산업',
    detail: '고용보험 상용 이력 · 2004.03 ~ 2026.09',
    is_recorded: false,
  },
  {
    import_id: 'cc_license_001',
    category: 'license',
    title: '지게차운전기능사',
    detail: '한국산업인력공단 · 2011.05.20 취득',
    is_recorded: false,
  },
  {
    import_id: 'cc_training_001',
    category: 'training',
    title: '용접 기초 과정',
    detail: '직업훈련 이수 · 2009.03 ~ 2009.06',
    is_recorded: false,
  },
];

const CHOI: ImportItem[] = [
  {
    import_id: 'cc_career_002',
    category: 'career',
    title: 'OO빌딩',
    detail: '고용보험 상용 이력 · 2022.07 ~ 2026.09',
    is_recorded: false,
  },
  {
    import_id: 'cc_career_001',
    category: 'career',
    title: 'OO아파트 관리사무소',
    detail: '고용보험 상용 이력 · 2010.03 ~ 2019.04',
    is_recorded: true,
  },
  {
    import_id: 'cc_license_001',
    category: 'license',
    title: '전기기능사',
    detail: '한국산업인력공단 · 2009.11.20 취득',
    is_recorded: true,
  },
];

const LEE: ImportItem[] = [
  {
    import_id: 'wa_001',
    category: 'job_search',
    title: 'OO물류 · 일반 사무',
    detail: '2026.12.08 고용24 입사지원 · 서류전형 심사진행 중',
    is_recorded: true,
  },
  {
    import_id: 'wa_003',
    category: 'job_search',
    title: 'OO물산 · 사무보조',
    detail: '2026.12.16 고용24 입사지원 · 서류전형 심사진행 중',
    is_recorded: false,
  },
];

export const MOCK_IMPORTS: Record<ImportKind, Record<string, ImportListRead>> = {
  'career-certificate': {
    park: { items: PARK, source_note: NOTE_CAREER },
    choi: { items: CHOI, source_note: NOTE_CAREER },
  },
  'work24-activities': {
    lee: { items: LEE, source_note: NOTE_WORK24 },
  },
};

const namesOf = (list: unknown, key: string): string[] =>
  Array.isArray(list)
    ? list.map((item) => String((item as Record<string, unknown>)?.[key] ?? '')).filter(Boolean)
    : [];

/**
 * 이미 패널에 들어간 항목은 `이미 넣음`으로 막습니다 (시연 검증 13번: 다시 불러오기에서 같은 항목을 또 고르지 않게).
 * 이름이 같으면 들어간 것으로 봅니다. 백엔드는 출처 ID로 같은 판단을 합니다.
 */
export const mockImportList = (
  list: ImportListRead,
  resume: Record<string, unknown>,
  activities: Record<string, unknown>,
): ImportListRead => {
  const competencies = (resume.competencies ?? {}) as Record<string, unknown>;
  const recorded = new Set([
    ...namesOf(competencies.careers, 'company_name'),
    ...namesOf(competencies.certifications, 'certificate_name'),
    ...namesOf(competencies.vocational_training, 'name'),
    ...namesOf(activities.activities, 'org_name'),
  ]);
  return {
    ...list,
    items: list.items.map((item) => ({
      ...item,
      is_recorded: item.is_recorded || recorded.has(item.title.split(' · ')[0]),
    })),
  };
};

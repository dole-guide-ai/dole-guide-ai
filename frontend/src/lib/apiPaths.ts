/**
 * 화면이 부르는 API 경로(BFF `/api` 뒤). 기능 훅과 mock 핸들러가 같은 값을 씁니다.
 * `LEGACY_*`는 백엔드가 아직 없는 예전 설계 경로라 mock만 응답합니다. 백엔드가 구현되면
 * 새 경로(`/accounts/{id}/...`)로 바꾸고 `lib/mockMode.ts`의 BACKEND_ROUTES에 더합니다.
 */
const account = (personaId: string) => `/accounts/${encodeURIComponent(personaId)}`;

export const API_PATHS = {
  health: '/health',
  personas: '/personas',
  account,
  messages: (personaId: string) => `${account(personaId)}/messages`,
  activities: (personaId: string) => `${account(personaId)}/activities`,
  activity: (personaId: string, activityId: string) =>
    `${account(personaId)}/activities/${activityId}`,
  currentRound: (personaId: string) => `${account(personaId)}/rounds/current`,
  recommendations: (personaId: string) => `${account(personaId)}/rounds/current/recommendations`,
  /** 회차 신청서. round가 없으면 지금 회차(`current`) */
  application: (personaId: string, round: number | null) =>
    `${account(personaId)}/rounds/${round ?? 'current'}/application`,
  /** 내 정보 (F-31). factId가 있으면 그 한 줄 */
  facts: (personaId: string, factId?: string) =>
    `${account(personaId)}/facts${factId ? `/${encodeURIComponent(factId)}` : ''}`,

  LEGACY_RESUME: '/forms/resume',
  LEGACY_RESUME_CONFIRM: '/forms/resume/confirm',
  LEGACY_RECOGNITION: '/forms/recognition',
  LEGACY_RECOGNITION_CONFIRM: '/forms/recognition/confirm',
  LEGACY_FILES: '/files',
  legacyImports: (kind: string) => `/imports/${kind}`,
} as const;

/** 화면이 부르는 API 경로(BFF `/api` 뒤). 계정 데이터는 모두 `/accounts/{id}/...`입니다. */
const account = (personaId: string) => `/accounts/${encodeURIComponent(personaId)}`;

export const API_PATHS = {
  health: '/health',
  personas: '/personas',
  account,
  messages: (personaId: string) => `${account(personaId)}/messages`,
  activities: (personaId: string) => `${account(personaId)}/activities`,
  files: (personaId: string) => `${account(personaId)}/files`,
  /** 말하기 녹음 → 글 */
  transcriptions: (personaId: string) => `${account(personaId)}/transcriptions`,
  imports: (personaId: string, path: string) => `${account(personaId)}/imports/${path}`,
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
} as const;

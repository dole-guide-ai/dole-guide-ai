export const queryKeys = {
  health: ['health'] as const,
  personas: ['personas'] as const,
  forms: ['forms'] as const,
  resumeForm: (sessionId: string) => ['forms', 'resume', sessionId] as const,
  procedure: ['procedure'] as const,
  imports: (kind: string, sessionId: string) => ['imports', kind, sessionId] as const,
  myData: (sessionId: string) => ['me', 'data', sessionId] as const,
  /** 회차가 바뀌어도 한꺼번에 무효화할 수 있게 회차 점검 키의 앞부분을 따로 둡니다. */
  roundCheckPrefix: (sessionId: string) => ['procedure', 'check', sessionId] as const,
  roundCheck: (sessionId: string, round: number | null) =>
    ['procedure', 'check', sessionId, round] as const,
  recognitionForm: (sessionId: string, round: number | null) =>
    ['forms', 'recognition', sessionId, round] as const,
  roundRecommendations: (sessionId: string) => ['procedure', 'recommendations', sessionId] as const,
};

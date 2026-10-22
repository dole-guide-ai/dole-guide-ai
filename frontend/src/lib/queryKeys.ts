export const queryKeys = {
  health: ['health'] as const,
  personas: ['personas'] as const,
  forms: ['forms'] as const,
  resumeForm: (sessionId: string) => ['forms', 'resume', sessionId] as const,
  procedure: ['procedure'] as const,
  imports: (kind: string, sessionId: string) => ['imports', kind, sessionId] as const,
  myData: (sessionId: string) => ['me', 'data', sessionId] as const,
  roundCheck: (sessionId: string, round: number | null) =>
    ['procedure', 'check', sessionId, round] as const,
  recognitionForm: (sessionId: string, round: number | null) =>
    ['forms', 'recognition', sessionId, round] as const,
  roundRecommendations: (sessionId: string) => ['procedure', 'recommendations', sessionId] as const,
};

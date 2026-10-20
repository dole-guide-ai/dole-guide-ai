export const queryKeys = {
  health: ['health'] as const,
  personas: ['personas'] as const,
  forms: ['forms'] as const,
  resumeForm: (sessionId: string) => ['forms', 'resume', sessionId] as const,
  procedure: ['procedure'] as const,
  roundCheck: (sessionId: string) => ['procedure', 'check', sessionId] as const,
  roundRecommendations: (sessionId: string) => ['procedure', 'recommendations', sessionId] as const,
};

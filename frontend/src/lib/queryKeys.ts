export const queryKeys = {
  health: ['health'] as const,
  personas: ['personas'] as const,
  forms: ['forms'] as const,
  resumeForm: (sessionId: string) => ['forms', 'resume', sessionId] as const,
};

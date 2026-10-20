import { useQuery } from '@tanstack/react-query';

import { apiFetch } from '@/lib/api';
import { queryKeys } from '@/lib/queryKeys';
import type { PersonaCardRead, SessionRead } from '@/types/demo.types';

/**
 * 세션 응답에는 이름이 없어서(개인 식별 칸을 두지 않음, 1.2) 카드 목록의 `display.name`을 찾아 씁니다.
 * 목록이 아직 없으면 빈 문자열입니다.
 */
export const usePersonaName = (session: SessionRead | null) => {
  const { data } = useQuery({
    queryKey: queryKeys.personas,
    queryFn: () => apiFetch<PersonaCardRead[]>('/auth/demo'),
    enabled: session !== null,
  });

  if (!session || !data) return '';
  return data.find((persona) => persona.persona_id === session.persona_id)?.display.name ?? '';
};

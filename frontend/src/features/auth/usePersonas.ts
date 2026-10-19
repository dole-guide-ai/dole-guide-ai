import { useQuery } from '@tanstack/react-query';

import { apiFetch } from '@/lib/api';
import { queryKeys } from '@/lib/queryKeys';
import type { PersonaCardRead } from '@/types/demo.types';

/** 로그인 카드 목록. 상태 값은 오지 않고 `display`만 옵니다 (1.11). */
export const usePersonas = () =>
  useQuery({
    queryKey: queryKeys.personas,
    queryFn: () => apiFetch<PersonaCardRead[]>('/auth/demo'),
  });

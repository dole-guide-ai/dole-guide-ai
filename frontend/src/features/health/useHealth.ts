import { useQuery } from '@tanstack/react-query';

import { apiFetch } from '@/lib/api';
import { API_PATHS } from '@/lib/apiPaths';
import { queryKeys } from '@/lib/queryKeys';
import type { components } from '@/types/api.gen';

type HealthRead = components['schemas']['HealthRead'];

export const useHealth = () =>
  useQuery({
    queryKey: queryKeys.health,
    queryFn: () => apiFetch<HealthRead>(API_PATHS.health),
  });

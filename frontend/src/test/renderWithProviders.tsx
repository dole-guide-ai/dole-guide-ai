import type { ReactElement } from 'react';

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, type RenderOptions } from '@testing-library/react';

import { BigTextProvider } from '@/features/bigText/BigTextProvider';

export const createTestQueryClient = () =>
  new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });

export const renderWithProviders = (ui: ReactElement, options?: RenderOptions) => {
  const queryClient = createTestQueryClient();
  return {
    queryClient,
    ...render(
      <QueryClientProvider client={queryClient}>
        <BigTextProvider>{ui}</BigTextProvider>
      </QueryClientProvider>,
      options,
    ),
  };
};

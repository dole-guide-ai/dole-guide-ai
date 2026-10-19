import { screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { HealthStatus } from '@/features/health/HealthStatus';

import { mockFetchJson } from '@/test/mockFetch';
import { renderWithProviders } from '@/test/renderWithProviders';

describe('HealthStatus', () => {
  it('서버와 DB 상태를 보여준다', async () => {
    mockFetchJson({ status: 'ok', db: 'ok' });

    renderWithProviders(<HealthStatus />);

    expect(await screen.findByText('서버 ok · DB ok')).toBeInTheDocument();
  });

  it('서버 응답이 실패하면 연결 실패를 보여준다', async () => {
    mockFetchJson({ detail: 'error' }, { status: 500 });

    renderWithProviders(<HealthStatus />);

    expect(await screen.findByText('서버 연결 실패')).toBeInTheDocument();
  });
});

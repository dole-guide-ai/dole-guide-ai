import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it } from 'vitest';

import { BigTextProvider } from '@/features/bigText/BigTextProvider';
import { BigTextToggle } from '@/features/bigText/BigTextToggle';

describe('BigTextToggle', () => {
  afterEach(() => {
    document.documentElement.dataset.bigText = 'false';
  });

  it('누르면 바로 루트의 글자 크기 표시가 바뀌고 문구가 다음 동작으로 바뀐다 (F-06)', async () => {
    render(
      <BigTextProvider>
        <BigTextToggle />
      </BigTextProvider>,
    );

    await userEvent.click(screen.getByRole('button', { name: '글자 크게' }));
    expect(document.documentElement.dataset.bigText).toBe('true');
    expect(screen.getByRole('button', { name: '글자 보통' })).toBeInTheDocument();

    await userEvent.click(screen.getByRole('button', { name: '글자 보통' }));
    expect(document.documentElement.dataset.bigText).toBe('false');
  });
});

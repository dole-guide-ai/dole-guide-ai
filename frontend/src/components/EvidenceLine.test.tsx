import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { EvidenceLine } from '@/components/EvidenceLine';

describe('EvidenceLine', () => {
  it('원문 링크가 없으면 근거 글자를 그대로 보여 줍니다', () => {
    render(<EvidenceLine cite="고용24 실업인정 안내" />);
    expect(screen.getByText(/고용24 실업인정 안내/)).toBeInTheDocument();
    expect(screen.queryByRole('link')).not.toBeInTheDocument();
  });

  it('원문 링크가 있으면 출처 이름을 새 창 링크로 보여 줍니다', () => {
    render(
      <EvidenceLine
        cite="고용노동부 1350 FAQ · 2021-09-17"
        links={[
          {
            title: '고용노동부 1350 FAQ',
            url: 'https://example.test/faq',
            updated_on: '2021-09-17',
          },
        ]}
      />,
    );
    const link = screen.getByRole('link', { name: '고용노동부 1350 FAQ' });
    expect(link).toHaveAttribute('href', 'https://example.test/faq');
    expect(link).toHaveAttribute('target', '_blank');
    expect(screen.getByText(/2021-09-17/)).toBeInTheDocument();
  });
});

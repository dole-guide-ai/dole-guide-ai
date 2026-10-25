import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { AssistantText } from '@/features/chat/AssistantText';

describe('AssistantText', () => {
  it('굵게와 번호 목록을 그린다', () => {
    const { container } = render(
      <AssistantText text={'**3건**이 남았어요.\n\n1. 지원\n2. 면접'} />,
    );

    expect(screen.getByText('3건').tagName).toBe('STRONG');
    expect(container.querySelectorAll('ol li')).toHaveLength(2);
  });

  it('이미지·링크·HTML은 그리지 않고 글자만 남긴다', () => {
    const { container } = render(
      <AssistantText
        text={'![x](https://example.com/a.png) [여기](https://example.com) <b>굵게</b>'}
      />,
    );

    expect(container.querySelector('img')).toBeNull();
    expect(container.querySelector('a')).toBeNull();
    expect(container.querySelector('b')).toBeNull();
    expect(container.textContent).toContain('여기');
  });

  it('한 줄 바꿈도 줄바꿈으로 그린다', () => {
    const { container } = render(<AssistantText text={'첫 줄\n둘째 줄'} />);

    expect(container.querySelector('br')).not.toBeNull();
  });
});

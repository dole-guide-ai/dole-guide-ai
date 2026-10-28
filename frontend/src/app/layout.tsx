import type { Metadata } from 'next';

import { THEME_INIT_SCRIPT } from '@/features/theme/theme';
import { Providers } from '@/app/providers';

import './globals.css';

export const metadata: Metadata = {
  title: '실업급여 길잡이',
  description: '음성이나 채팅으로 이야기하면 고용24 서류를 완성해 주는 실업급여 행정 도우미',
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    // data-theme은 첫 그림 전에 스크립트가 정하므로 서버 HTML과 달라도 경고를 내지 않습니다.
    <html lang="ko" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: THEME_INIT_SCRIPT }} />
      </head>
      <body className="antialiased">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}

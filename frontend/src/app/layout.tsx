import type { Metadata } from 'next';

import { Providers } from '@/app/providers';

import './globals.css';

export const metadata: Metadata = {
  title: '실업급여 도우미 AI',
  description: '말로 이야기하면 고용24 서류를 완성해 주는 실업급여 행정 도우미',
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="ko">
      <body className="antialiased">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}

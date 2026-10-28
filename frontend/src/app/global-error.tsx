'use client';

import { RotateCcw, TriangleAlert } from 'lucide-react';

import { Button, buttonClassName } from '@/components/Button';
import { ErrorState } from '@/components/ErrorState';
import { THEME_INIT_SCRIPT } from '@/features/theme/theme';

import { ICON_SIZE, ICON_STROKE } from '@/lib/iconSize';

import './globals.css';

/**
 * 루트 레이아웃까지 실패했을 때 쓰는 마지막 경계. 레이아웃을 대신하므로 html·body·전역 스타일·테마 스크립트를 직접 둡니다.
 */
export default function GlobalError({
  error,
  retry,
}: {
  error: Error & { digest?: string };
  retry: () => void;
}) {
  return (
    <html lang="ko" suppressHydrationWarning>
      <head>
        <title>실업급여 길잡이</title>
        <script dangerouslySetInnerHTML={{ __html: THEME_INIT_SCRIPT }} />
      </head>
      <body className="antialiased">
        <ErrorState
          icon={TriangleAlert}
          title="서비스를 열지 못했어요"
          description="잠시 문제가 생겼어요. 다시 시도해도 같으면 처음 화면부터 다시 열어 주세요."
          digest={error.digest}
          actions={
            <>
              <Button onClick={retry}>
                <RotateCcw aria-hidden size={ICON_SIZE.md} strokeWidth={ICON_STROKE} />
                다시 시도하기
              </Button>
              {/* 앱 상태를 새로 시작하도록 Link 대신 문서 전체를 다시 엽니다. */}
              {/* eslint-disable-next-line @next/next/no-html-link-for-pages */}
              <a href="/" className={buttonClassName('secondary')}>
                처음 화면으로 가기
              </a>
            </>
          }
        />
      </body>
    </html>
  );
}

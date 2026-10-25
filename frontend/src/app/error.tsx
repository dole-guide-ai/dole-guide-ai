'use client';

import Link from 'next/link';

import { RotateCcw, TriangleAlert } from 'lucide-react';

import { Button, buttonClassName } from '@/components/Button';
import { ErrorState } from '@/components/ErrorState';

import { ICON_SIZE, ICON_STROKE } from '@/lib/iconSize';

/** 화면을 그리다 난 오류를 받는 경계. 원문 오류는 사용자에게 보이지 않고, 다시 시도하거나 처음 화면으로 갈 수 있습니다. */
export default function Error({
  error,
  retry,
}: {
  error: Error & { digest?: string };
  retry: () => void;
}) {
  return (
    <ErrorState
      icon={TriangleAlert}
      title="화면을 보여 드리지 못했어요"
      description="잠시 문제가 생겼어요. 다시 시도해도 같으면 처음 화면에서 계정을 다시 골라 주세요."
      digest={error.digest}
      actions={
        <>
          <Button onClick={retry}>
            <RotateCcw aria-hidden size={ICON_SIZE.md} strokeWidth={ICON_STROKE} />
            다시 시도하기
          </Button>
          <Link href="/" className={buttonClassName('secondary')}>
            처음 화면으로 가기
          </Link>
        </>
      }
    />
  );
}

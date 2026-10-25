import Link from 'next/link';

import { MapPinOff } from 'lucide-react';

import { buttonClassName } from '@/components/Button';
import { ErrorState } from '@/components/ErrorState';

/** 없는 주소로 들어왔을 때 (404). */
export default function NotFound() {
  return (
    <ErrorState
      icon={MapPinOff}
      title="찾는 화면이 없어요"
      description="주소가 바뀌었거나 없는 화면이에요. 처음 화면에서 다시 시작해 주세요."
      actions={
        <Link href="/" className={buttonClassName()}>
          처음 화면으로 가기
        </Link>
      }
    />
  );
}

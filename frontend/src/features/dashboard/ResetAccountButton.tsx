'use client';

import { RotateCcw } from 'lucide-react';

import { Button } from '@/components/Button';
import { useResetAccount } from '@/features/dashboard/useResetAccount';

import { ICON_SIZE, ICON_STROKE } from '@/lib/iconSize';

const CONFIRM_TEXT = '이 계정의 이력서·신청서·활동·대화를 모두 지우고 처음 상태로 돌아갈까요?';

interface ResetAccountButtonProps {
  personaId: string;
}

/** "처음부터 다시" 버튼. 확인을 받은 뒤 이 계정을 seed 상태로 되돌립니다(시연을 다시 시작할 때). */
export const ResetAccountButton = ({ personaId }: ResetAccountButtonProps) => {
  const reset = useResetAccount(personaId);

  return (
    <Button
      variant="ghost"
      disabled={reset.isPending}
      onClick={() => {
        if (window.confirm(CONFIRM_TEXT)) reset.mutate();
      }}
    >
      <RotateCcw aria-hidden size={ICON_SIZE.md} strokeWidth={ICON_STROKE} />
      {reset.isPending ? '지우는 중…' : '처음부터 다시'}
    </Button>
  );
};

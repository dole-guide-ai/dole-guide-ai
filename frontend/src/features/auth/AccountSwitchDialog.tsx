'use client';

import { useEffect, useRef } from 'react';

import { X } from 'lucide-react';

import { PersonaList } from '@/features/auth/PersonaList';

import { ICON_SIZE, ICON_STROKE } from '@/lib/iconSize';

/**
 * 대시보드 `계정 바꾸기` 창: 로그인 화면과 같은 가상 계정 카드를 띄워 바로 다른 계정으로 들어갑니다.
 * 지금 계정은 표시만 하고 고를 수 없고, 다른 계정에 들어가면 창이 닫힙니다. Esc·닫기로도 닫힙니다.
 * 네이티브 `<dialog>`를 `showModal()`로 열어 바깥을 막고 Tab 이동을 창 안에 둡니다. 닫히면 연 버튼으로 포커스를 돌려줍니다.
 */
interface AccountSwitchDialogProps {
  currentPersonaId: string;
  onClose: () => void;
}

export const AccountSwitchDialog = ({ currentPersonaId, onClose }: AccountSwitchDialogProps) => {
  const dialogRef = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const dialog = dialogRef.current;
    // 창을 연 요소(계정 바꾸기 버튼)를 기억했다가 닫힐 때 포커스를 돌려줍니다.
    const opener = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    dialog?.showModal();
    return () => {
      if (dialog?.open) dialog.close();
      opener?.focus();
    };
  }, []);

  return (
    <dialog
      ref={dialogRef}
      aria-labelledby="account-switch-title"
      // Esc는 브라우저가 창을 닫기 전에 cancel을 보내므로, 상태로 닫도록 넘깁니다.
      onCancel={(event) => {
        event.preventDefault();
        onClose();
      }}
      className="bg-surface text-ink m-auto max-h-[90dvh] w-full max-w-5xl overflow-y-auto rounded-2xl p-6 shadow-lg backdrop:bg-black/50"
    >
      <div className="flex flex-col gap-4">
        <div className="flex items-start justify-between gap-3">
          <div className="flex flex-col gap-1">
            <h2 id="account-switch-title" className="text-xl font-bold">
              계정 바꾸기
            </h2>
            <p className="text-muted text-base">
              다른 가상 계정을 고르면 그 사람의 상황으로 바로 바뀌어요.
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="계정 바꾸기 닫기"
            className="text-muted hover:bg-neutral-soft hover:text-ink focus-visible:ring-brand inline-flex size-10 shrink-0 items-center justify-center rounded-full focus-visible:ring-3 focus-visible:outline-hidden"
          >
            <X aria-hidden size={ICON_SIZE.lg} strokeWidth={ICON_STROKE} />
          </button>
        </div>
        <PersonaList currentPersonaId={currentPersonaId} onSelected={onClose} />
      </div>
    </dialog>
  );
};

'use client';

import { useEffect } from 'react';

import { Button } from '@/components/Button';
import { useDeleteMyData } from '@/features/myData/useDeleteMyData';
import { useMyData } from '@/features/myData/useMyData';

import { ApiError } from '@/lib/api';
import { formatDotDate } from '@/lib/dateFormat';
import type { MyDataGroup } from '@/types/myData.types';

/**
 * 내 정보 (2-0.9): 확정된 값 요약 · 절차 상태 · 이용자가 확인한 사실을 보여 주고 줄마다 지울 수 있습니다.
 * 지우면 그 값을 쓰던 패널 칸이 `아직 없음`으로 돌아갑니다. 저장하지 않는 정보도 함께 알려 줍니다.
 */
interface MyDataDialogProps {
  sessionId: string;
  onClose: () => void;
}

const GROUP_TITLE: Record<MyDataGroup, string> = {
  resume: '작성한 서류',
  procedure: '절차 상태',
  facts: '이용자가 확인한 사실',
};

const GROUPS: MyDataGroup[] = ['resume', 'procedure', 'facts'];

const errorText = (error: unknown, fallback: string) =>
  error instanceof ApiError ? error.message : fallback;

export const MyDataDialog = ({ sessionId, onClose }: MyDataDialogProps) => {
  const query = useMyData(sessionId, true);
  const remove = useDeleteMyData(sessionId);

  useEffect(() => {
    const handleKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handleKey);
    return () => window.removeEventListener('keydown', handleKey);
  }, [onClose]);

  return (
    <div className="bg-ink/40 fixed inset-0 z-50 flex items-center justify-center p-4">
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="my-data-title"
        className="bg-surface flex max-h-[90dvh] w-full max-w-xl flex-col gap-4 overflow-y-auto rounded-2xl p-6 shadow-lg"
      >
        <div className="flex items-center justify-between gap-3">
          <h2 id="my-data-title" className="text-xl font-bold">
            내 정보
          </h2>
          <Button variant="ghost" onClick={onClose}>
            닫기
          </Button>
        </div>

        {query.isPending && <p className="text-muted text-base">불러오는 중…</p>}
        {query.isError && (
          <p role="alert" className="text-danger text-base">
            {errorText(query.error, '내 정보를 불러오지 못했어요.')}
          </p>
        )}

        {query.data &&
          GROUPS.map((group) => {
            const items = query.data.items.filter((item) => item.group === group);
            return (
              <section key={group} className="flex flex-col gap-1" aria-label={GROUP_TITLE[group]}>
                <h3 className="text-muted text-sm font-semibold">{GROUP_TITLE[group]}</h3>
                {items.length === 0 ? (
                  <p className="text-muted text-base">저장된 정보가 없어요.</p>
                ) : (
                  <ul className="divide-line divide-y">
                    {items.map((item) => (
                      <li key={item.item_id} className="flex flex-wrap items-center gap-3 py-2">
                        <span className="text-muted w-32 shrink-0 text-sm">{item.label}</span>
                        <span className="min-w-0 flex-1 text-base">
                          {item.value}
                          {item.confirmed_on && (
                            <span className="text-muted text-sm">
                              {' '}
                              · {formatDotDate(item.confirmed_on)} 확인
                            </span>
                          )}
                        </span>
                        {item.is_deletable && (
                          <Button
                            variant="secondary"
                            onClick={() => remove.mutate({ item_id: item.item_id })}
                            disabled={remove.isPending}
                            aria-label={`${item.label} 삭제`}
                          >
                            삭제
                          </Button>
                        )}
                      </li>
                    ))}
                  </ul>
                )}
              </section>
            );
          })}

        {remove.isError && (
          <p role="alert" className="text-danger text-sm">
            {errorText(remove.error, '지우지 못했어요.')}
          </p>
        )}
        {query.data && (
          <p className="bg-canvas text-muted rounded-xl px-4 py-3 text-sm">
            저장하지 않는 정보 · {query.data.not_stored.join(', ')}. 지운 정보는 필요할 때 AI가 다시
            물어요.
          </p>
        )}
      </div>
    </div>
  );
};

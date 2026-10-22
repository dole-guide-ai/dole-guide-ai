'use client';

import { useState } from 'react';

import { PastRoundApplication } from '@/features/procedure/PastRoundApplication';
import { usePastRounds } from '@/features/procedure/usePastRounds';

import { isServerSession } from '@/lib/accountSession';
import { formatShortDate } from '@/lib/dateFormat';
import type { SessionRead } from '@/types/demo.types';

interface PastRoundsProps {
  session: SessionRead;
}

/**
 * 지난 회차 신청서 다시 보기 (F-04, 1.8 읽기 전용). 실제 서버 세션에서만 보입니다.
 * 모의 세션은 지난 회차 신청서를 따로 두지 않습니다.
 */
export const PastRounds = ({ session }: PastRoundsProps) => {
  const isServer = isServerSession(session.session_id);
  const query = usePastRounds(session.persona_id, isServer);
  const [openRound, setOpenRound] = useState<number | null>(null);

  if (!isServer || !query.data?.length) return null;

  return (
    <section aria-label="지난 회차 신청서" className="flex flex-col gap-2">
      <h3 className="text-lg font-bold">지난 회차 신청서</h3>
      <ul className="flex flex-col gap-2">
        {query.data.map((round) => {
          const isOpen = openRound === round.round;
          return (
            <li key={round.round} className="border-line rounded-xl border px-4 py-3">
              <button
                type="button"
                aria-expanded={isOpen}
                className="flex w-full items-center justify-between text-left text-base font-semibold"
                onClick={() => setOpenRound(isOpen ? null : round.round)}
              >
                <span>
                  {round.round}차 · {formatShortDate(round.recognition_date)}
                </span>
                <span className="text-muted text-sm">
                  {round.application_status === 'submitted' ? '제출함' : '제출 기록 없음'}
                </span>
              </button>
              {isOpen && (
                <div className="mt-2">
                  <PastRoundApplication personaId={session.persona_id} round={round.round} />
                </div>
              )}
            </li>
          );
        })}
      </ul>
    </section>
  );
};

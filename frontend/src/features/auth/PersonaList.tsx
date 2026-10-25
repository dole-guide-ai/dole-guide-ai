'use client';

import { Spinner } from '@/components/Spinner';
import { PersonaCard } from '@/features/auth/PersonaCard';
import { useDemoLogin } from '@/features/auth/useDemoLogin';
import { usePersonas } from '@/features/auth/usePersonas';

/** 가상 계정 카드 목록. 로그인 화면과 대시보드의 `계정 바꾸기` 창이 같이 씁니다. */
interface PersonaListProps {
  /** 지금 쓰는 계정. 카드에 `지금 계정`을 표시하고 다시 고를 수 없게 합니다. */
  currentPersonaId?: string;
  /** 계정에 들어간 뒤 (예: 계정 바꾸기 창 닫기) */
  onSelected?: () => void;
}

export const PersonaList = ({ currentPersonaId, onSelected }: PersonaListProps) => {
  const { data, isPending, isError } = usePersonas();
  const login = useDemoLogin();

  if (isPending) return <Spinner label="계정을 불러오는 중…" isCentered />;
  if (isError)
    return (
      <p className="text-danger text-lg" role="alert">
        계정 목록을 불러오지 못했어요. 서버 연결을 확인해 주세요.
      </p>
    );

  return (
    <div className="flex flex-col gap-3">
      <ul className="grid gap-3 lg:grid-cols-3" aria-busy={login.isPending}>
        {data.map((persona) => (
          <li key={persona.persona_id}>
            <PersonaCard
              persona={persona}
              onSelect={(personaId) => login.mutate(personaId, { onSuccess: onSelected })}
              isDisabled={login.isPending}
              isCurrent={persona.persona_id === currentPersonaId}
            />
          </li>
        ))}
      </ul>
      {login.isError && (
        <p className="text-danger text-base" role="alert">
          시작하지 못했어요. 잠시 후 다시 눌러 주세요.
        </p>
      )}
    </div>
  );
};

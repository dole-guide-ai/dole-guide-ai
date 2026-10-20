'use client';

import { PersonaCard } from '@/features/auth/PersonaCard';
import { useDemoLogin } from '@/features/auth/useDemoLogin';
import { usePersonas } from '@/features/auth/usePersonas';

export const PersonaList = () => {
  const { data, isPending, isError } = usePersonas();
  const login = useDemoLogin();

  if (isPending) return <p className="text-muted text-lg">계정을 불러오는 중…</p>;
  if (isError)
    return (
      <p className="text-danger text-lg" role="alert">
        계정 목록을 불러오지 못했어요. 서버 연결을 확인해 주세요.
      </p>
    );

  return (
    <div className="flex flex-col gap-3">
      <ul className="flex max-h-[60vh] flex-col gap-3 overflow-y-auto" aria-busy={login.isPending}>
        {data.map((persona) => (
          <li key={persona.persona_id}>
            <PersonaCard persona={persona} onSelect={login.mutate} isDisabled={login.isPending} />
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

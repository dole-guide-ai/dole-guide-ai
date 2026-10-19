'use client';

import { useHealth } from '@/features/health/useHealth';

export const HealthStatus = () => {
  const { data, isPending, isError } = useHealth();

  if (isPending) return <p className="text-lg text-gray-500">서버 확인 중…</p>;
  if (isError) return <p className="text-lg text-red-600">서버 연결 실패</p>;

  return (
    <p className="text-lg text-green-700">
      서버 {data.status} · DB {data.db}
    </p>
  );
};

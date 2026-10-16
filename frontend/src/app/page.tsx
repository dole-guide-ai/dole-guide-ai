import { HealthStatus } from '@/features/health/HealthStatus';

export default function Home() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-4 p-8">
      <h1 className="text-3xl font-bold">실업급여 도우미 AI</h1>
      <HealthStatus />
    </main>
  );
}

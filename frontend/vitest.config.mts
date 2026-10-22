import react from '@vitejs/plugin-react';
import tsconfigPaths from 'vite-tsconfig-paths';
import { defineConfig } from 'vitest/config';

export default defineConfig({
  plugins: [tsconfigPaths(), react()],
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    include: ['src/**/*.test.{ts,tsx}'],
    css: false,
    // 테스트는 fetch를 직접 대체하므로 모의 응답 없이 실제 호출 경로를 씁니다.
    env: { NEXT_PUBLIC_USE_MOCK: '0' },
    coverage: {
      provider: 'v8',
      include: ['src/**/*.{ts,tsx}'],
      exclude: ['src/test/**', 'src/types/api.gen.ts', 'src/**/*.test.{ts,tsx}'],
    },
  },
});

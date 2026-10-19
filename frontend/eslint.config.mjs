import { defineConfig, globalIgnores } from 'eslint/config';
import nextVitals from 'eslint-config-next/core-web-vitals';
import nextTs from 'eslint-config-next/typescript';
import prettier from 'eslint-config-prettier';
import simpleImportSort from 'eslint-plugin-simple-import-sort';

export default defineConfig([
  ...nextVitals,
  ...nextTs,
  {
    plugins: { 'simple-import-sort': simpleImportSort },
    rules: {
      // React·Next → 외부 라이브러리 → 내부 컴포넌트 → 유틸·타입 → 에셋
      'simple-import-sort/imports': [
        'error',
        {
          groups: [
            ['^react', '^next'],
            ['^@?\\w'],
            ['^@/components', '^@/features', '^@/app'],
            ['^@/lib', '^@/types', '^@/'],
            ['^\\u0000', '^\\.', '\\.(css|svg|png|jpg|jpeg|gif|webp)$'],
          ],
        },
      ],
      'simple-import-sort/exports': 'error',
      '@typescript-eslint/consistent-type-definitions': ['error', 'interface'],
    },
  },
  {
    // 서버 호출은 lib/api.ts의 apiFetch만 씁니다. (오류를 ApiError로 통일)
    files: ['src/**/*.{ts,tsx}'],
    ignores: ['src/lib/api.ts', 'src/lib/sse.ts', 'src/**/*.test.{ts,tsx}', 'src/test/**'],
    rules: {
      'no-restricted-globals': [
        'error',
        { name: 'fetch', message: '서버 호출은 @/lib/api의 apiFetch를 쓰세요.' },
      ],
      'no-restricted-properties': [
        'error',
        {
          object: 'window',
          property: 'fetch',
          message: '서버 호출은 @/lib/api의 apiFetch를 쓰세요.',
        },
        {
          object: 'globalThis',
          property: 'fetch',
          message: '서버 호출은 @/lib/api의 apiFetch를 쓰세요.',
        },
      ],
    },
  },
  prettier,
  globalIgnores(['.next/**', 'out/**', 'build/**', 'next-env.d.ts', 'src/types/api.gen.ts']),
]);

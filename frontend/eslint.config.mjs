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
  prettier,
  globalIgnores(['.next/**', 'out/**', 'build/**', 'next-env.d.ts', 'src/types/api.gen.ts']),
]);

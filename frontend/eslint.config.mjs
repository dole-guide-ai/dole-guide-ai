import { FlatCompat } from '@eslint/eslintrc';
import prettier from 'eslint-config-prettier';
import simpleImportSort from 'eslint-plugin-simple-import-sort';
import { dirname } from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

const compat = new FlatCompat({
  baseDirectory: __dirname,
});

const eslintConfig = [
  ...compat.extends('next/core-web-vitals', 'next/typescript'),
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
  {
    ignores: [
      'node_modules/**',
      '.next/**',
      'out/**',
      'build/**',
      'next-env.d.ts',
      'src/types/api.gen.ts',
    ],
  },
];

export default eslintConfig;

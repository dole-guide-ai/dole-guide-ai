// pnpm install 때 lefthook Git 훅을 설치합니다.
// Vercel·CI처럼 .git이 없거나 훅이 필요 없는 환경에서는 건너뜁니다. (macOS·Windows 공용)
import { spawnSync } from 'node:child_process';
import { existsSync } from 'node:fs';
import path from 'node:path';

const ROOT = path.resolve(import.meta.dirname, '..');

if (process.env.CI || process.env.VERCEL || !existsSync(path.join(ROOT, '.git'))) {
  process.exit(0);
}

const res = spawnSync('pnpm', ['exec', 'lefthook', 'install'], {
  cwd: ROOT,
  stdio: 'inherit',
  shell: process.platform === 'win32',
});
process.exit(res.status ?? 1);

// Claude가 파일을 수정한 직후 실행됩니다 (PostToolUse).
// 수정한 파일만 린트·포맷하고, 그 파일과 관련된 단위 테스트만 돌립니다.
// 실패하면 exit 2로 결과를 Claude에게 돌려줘 바로 고치게 합니다. macOS·Windows 공용.
import { spawnSync } from 'node:child_process';
import { existsSync, readdirSync, readFileSync } from 'node:fs';
import path from 'node:path';

const ROOT = path.resolve(import.meta.dirname, '..', '..');
const FRONTEND = path.join(ROOT, 'frontend');
const BACKEND = path.join(ROOT, 'backend');
const TIMEOUT_MS = 60_000;

const SKIP = [
  /(^|\/)pnpm-lock\.yaml$/,
  /(^|\/)uv\.lock$/,
  /^frontend\/src\/types\/api\.gen\.ts$/,
  /^backend\/alembic\/versions\//,
];

const input = JSON.parse(readFileSync(0, 'utf8') || '{}');
const filePath = input.tool_input?.file_path;
if (!filePath || !existsSync(filePath)) process.exit(0);

const rel = path.relative(ROOT, path.resolve(filePath)).split(path.sep).join('/');
if (rel.startsWith('..') || SKIP.some((re) => re.test(rel))) process.exit(0);

const failures = [];

const isWindows = process.platform === 'win32';

const run = (label, cmd, args, cwd) => {
  const shellArgs = isWindows ? args.map((a) => (/\s/.test(a) ? `"${a}"` : a)) : args;
  const res = spawnSync(cmd, shellArgs, {
    cwd,
    encoding: 'utf8',
    timeout: TIMEOUT_MS,
    shell: isWindows,
    env: { ...process.env, PYTHONUTF8: '1', FORCE_COLOR: '0', NO_COLOR: '1' },
  });
  if (res.status !== 0) {
    const output = `${res.stdout ?? ''}${res.stderr ?? ''}`.trim().split('\n').slice(-40).join('\n');
    failures.push(`[${label}] 실패\n${output || res.error?.message || ''}`);
  }
  return res.status === 0;
};

const findPythonTests = (stem) => {
  const found = [];
  const walk = (dir) => {
    for (const entry of readdirSync(dir, { withFileTypes: true })) {
      const full = path.join(dir, entry.name);
      if (entry.isDirectory()) walk(full);
      else if (entry.name === `test_${stem}.py`) found.push(full);
    }
  };
  const unitDir = path.join(BACKEND, 'tests', 'unit');
  if (existsSync(unitDir)) walk(unitDir);
  return found;
};

if (rel.startsWith('frontend/')) {
  const target = path.relative(FRONTEND, path.join(ROOT, rel));
  if (/\.(ts|tsx|js|mjs)$/.test(rel)) {
    run('eslint', 'pnpm', ['exec', 'eslint', '--fix', target], FRONTEND);
    run('prettier', 'pnpm', ['exec', 'prettier', '--write', '--log-level', 'warn', target], FRONTEND);
    if (rel.startsWith('frontend/src/')) {
      run('vitest', 'pnpm', ['exec', 'vitest', 'related', target, '--run', '--passWithNoTests'], FRONTEND);
    }
  } else if (/\.(css|json|md)$/.test(rel)) {
    run('prettier', 'pnpm', ['exec', 'prettier', '--write', '--log-level', 'warn', target], FRONTEND);
  }
} else if (rel.startsWith('backend/') && rel.endsWith('.py')) {
  const target = path.relative(BACKEND, path.join(ROOT, rel));
  run('ruff check', 'uv', ['run', 'ruff', 'check', '--fix', target], BACKEND);
  run('ruff format', 'uv', ['run', 'ruff', 'format', target], BACKEND);

  const name = path.basename(rel, '.py');
  const stem = name === '__init__' ? path.basename(path.dirname(rel)) : name;
  const tests = name.startsWith('test_') ? [target] : findPythonTests(stem).map((t) => path.relative(BACKEND, t));
  if (tests.length > 0 && !rel.startsWith('backend/evals/') && !rel.startsWith('backend/tests/integration/')) {
    run('pytest', 'uv', ['run', 'pytest', '-q', '--color=no', '-m', 'not integration and not eval', ...tests], BACKEND);
  }
}

if (failures.length > 0) {
  console.error(`${rel} 수정 후 검사 결과:\n\n${failures.join('\n\n')}`);
  process.exit(2);
}

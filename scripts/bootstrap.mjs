// 처음 세팅을 한 번에 합니다: 도구 확인 → .env 복사 → 백엔드 의존성 → DB 실행 → 마이그레이션.
// 사용: pnpm bootstrap (macOS·Windows 공용). 이미 있는 .env 파일은 덮어쓰지 않습니다.
import { spawnSync } from 'node:child_process';
import { copyFileSync, existsSync } from 'node:fs';
import path from 'node:path';

const ROOT = path.resolve(import.meta.dirname, '..');
const isWindows = process.platform === 'win32';

const exec = (cmd, args, options = {}) =>
  spawnSync(cmd, args, { cwd: ROOT, encoding: 'utf8', shell: isWindows, ...options });

const step = (title) => console.log(`\n▶ ${title}`);

const fail = (message) => {
  console.error(`\n✖ ${message}`);
  process.exit(1);
};

const runOrFail = (title, cmd, args, options) => {
  step(title);
  const res = exec(cmd, args, { stdio: 'inherit', ...options });
  if (res.status !== 0) fail(`${title} 실패`);
};

step('도구 확인');
const TOOLS = [
  ['node', ['--version'], 'mise install (mise.toml 기준)'],
  ['pnpm', ['--version'], 'mise install (mise.toml 기준)'],
  ['uv', ['--version'], 'mise install (mise.toml 기준)'],
  ['docker', ['--version'], 'Docker Desktop 설치 후 실행'],
];
for (const [cmd, args, hint] of TOOLS) {
  const res = exec(cmd, args);
  if (res.status !== 0) fail(`${cmd}가 없습니다. 설치: ${hint}`);
  console.log(`  ${cmd}: ${res.stdout.trim().split('\n')[0]}`);
}
const nodeMajor = Number(process.versions.node.split('.')[0]);
if (nodeMajor < 22) fail(`Node 22 이상이 필요합니다. 현재 ${process.versions.node}`);

step('.env 파일 준비');
for (const [example, target] of [
  ['backend/.env.example', 'backend/.env'],
  ['frontend/.env.example', 'frontend/.env.local'],
]) {
  const targetPath = path.join(ROOT, target);
  if (existsSync(targetPath)) {
    console.log(`  ${target} 있음 (유지)`);
  } else {
    copyFileSync(path.join(ROOT, example), targetPath);
    console.log(`  ${target} 생성 (${example} 복사) — 필요한 값을 채워 주세요`);
  }
}

runOrFail('백엔드 의존성 설치 (uv sync)', 'uv', ['sync', '--directory', 'backend']);

step('DB 실행 (docker compose up -d db)');
if (exec('docker', ['info']).status !== 0) fail('Docker가 실행 중이 아닙니다. Docker Desktop을 켜고 다시 실행하세요.');
runOrFail('DB 컨테이너 시작', 'docker', ['compose', 'up', '-d', 'db']);

step('DB 준비 대기');
let ready = false;
for (let i = 0; i < 30 && !ready; i += 1) {
  ready = exec('docker', ['compose', 'exec', '-T', 'db', 'pg_isready', '-U', 'dole']).status === 0;
  if (!ready) Atomics.wait(new Int32Array(new SharedArrayBuffer(4)), 0, 0, 2000);
}
if (!ready) fail('DB가 60초 안에 준비되지 않았습니다. `docker compose logs db`를 확인하세요.');

runOrFail('마이그레이션 (alembic upgrade head)', 'uv', ['run', '--directory', 'backend', 'alembic', 'upgrade', 'head']);

console.log(`
✔ 세팅 완료

  pnpm dev:be   # 백엔드  http://localhost:8000/docs
  pnpm dev:fe   # 프론트  http://localhost:3000
  pnpm test     # 테스트
`);

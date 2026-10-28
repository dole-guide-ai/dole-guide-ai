// PR 추가 줄 수 검사 (규칙: +1000줄 이내). 자동 생성 파일은 제외합니다.
// 사용: node scripts/check-pr-size.mjs [기준 브랜치=origin/develop]
import { execFileSync } from 'node:child_process';

const LIMIT = 1000;
const base = process.argv[2] ?? 'origin/develop';
const EXCLUDED = [
  /(^|\/)pnpm-lock\.yaml$/,
  /(^|\/)uv\.lock$/,
  /^frontend\/src\/types\/api\.gen\.ts$/,
  /^backend\/alembic\/versions\//,
  /^backend\/data\/reference\/work24_codes\.json$/, // scripts/fetch_work24_codes.py가 만듦
  /^backend\/data\/rules\/rule_questions\.csv$/, // scripts/generate_rule_questions.py가 만듦
  /^backend\/evals\/retrieval\/guide_queries\.jsonl$/, // scripts/generate_guide_questions.py가 만듦
];

const out = execFileSync('git', ['diff', '--numstat', `${base}...HEAD`], { encoding: 'utf8' });

let total = 0;
for (const line of out.split('\n').filter(Boolean)) {
  const [added, , file] = line.split('\t');
  if (added === '-' || EXCLUDED.some((re) => re.test(file))) continue;
  total += Number(added);
}

console.log(`추가된 줄: ${total} / ${LIMIT} (자동 생성 파일 제외, 기준 ${base})`);
if (total > LIMIT) {
  console.error('PR이 너무 큽니다. 이슈를 나눠 여러 PR로 올려 주세요.');
  process.exit(1);
}

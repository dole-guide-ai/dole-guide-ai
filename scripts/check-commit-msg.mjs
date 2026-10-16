// lefthook commit-msg 훅. 셸 없이 Node로 검사해 윈도우에서도 동일하게 동작합니다.
import { readFileSync } from 'node:fs';

const TYPES = 'feat|fix|refactor|style|design|docs|test|chore|ci';
const SCOPES = 'fe|be|ai|infra|docs';
const PATTERN = new RegExp(`^(${TYPES})\\((${SCOPES})\\)!?: .+`);

const file = process.argv[2];
const firstLine = readFileSync(file, 'utf8').split(/\r?\n/)[0].trim();

if (PATTERN.test(firstLine) || /^(Merge|Revert)/.test(firstLine)) process.exit(0);

console.error("커밋 메시지는 'type(scope): 무엇을 왜' 형식이어야 합니다. (docs/CONVENTIONS.md 참고)");
console.error(`  type: ${TYPES.replaceAll('|', ', ')}`);
console.error(`  scope: ${SCOPES.replaceAll('|', ', ')}`);
console.error(`  입력값: ${firstLine}`);
process.exit(1);

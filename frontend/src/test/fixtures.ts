import { vi } from 'vitest';

/**
 * 테스트 픽스처: 실제 백엔드가 seed 계정(합성 값)으로 돌려준 응답을 그대로 떠 둔 것입니다
 * (오늘 2026-10-21, `src/test/fixtures/*.json`). 목(mock) 대신 이 응답 모양으로 화면을 시험합니다.
 * 백엔드 응답이 바뀌면 다시 떠야 합니다.
 */
import { sessionFromAccount } from '@/lib/accountSession';
import type { components } from '@/types/api.gen';
import type { SessionRead } from '@/types/demo.types';

import accountChoi from './fixtures/account_choi.json';
import accountLee from './fixtures/account_lee.json';
import accountPark from './fixtures/account_park.json';
import applicationLee from './fixtures/application_lee.json';
import personas from './fixtures/personas.json';
import resumeChoi from './fixtures/resume_choi.json';
import resumeLee from './fixtures/resume_lee.json';
import resumePark from './fixtures/resume_park.json';
import roundCheckLee from './fixtures/round_check_lee.json';

type Schemas = components['schemas'];

export type PersonaId = 'park' | 'choi' | 'lee';

export const PERSONAS = personas as Schemas['PersonaList'];

export const ACCOUNTS: Record<PersonaId, Schemas['AccountRead']> = {
  park: accountPark as Schemas['AccountRead'],
  choi: accountChoi as Schemas['AccountRead'],
  lee: accountLee as Schemas['AccountRead'],
};

export const RESUMES: Record<PersonaId, Schemas['ResumeRead']> = {
  park: resumePark as Schemas['ResumeRead'],
  choi: resumeChoi as Schemas['ResumeRead'],
  lee: resumeLee as Schemas['ResumeRead'],
};

export const LEE_APPLICATION = applicationLee as Schemas['ApplicationRead'];
export const LEE_ROUND_CHECK_SNAPSHOT = roundCheckLee as Schemas['RoundCheck'];

/** 계정에 입장한 화면 세션 (실제 입장 응답에서 만든 것) */
export const sessionFor = (personaId: PersonaId): SessionRead =>
  sessionFromAccount(ACCOUNTS[personaId]);

/**
 * 이력서 API 가짜 서버: `GET /accounts/{id}/resume`은 떠 둔 응답(ETag 포함), `PATCH`는 받은 연산을 기록하고
 * 저장(`/status` → saved)이면 다음 단계 첫 안내(E6)를 돌려줍니다. `GET /accounts/{id}`는 계정 응답입니다.
 */
export const mockResumeApi = (
  personaId: PersonaId,
  resume: Schemas['ResumeRead'] = RESUMES[personaId],
) => {
  const patches: unknown[] = [];
  const spy = vi.spyOn(globalThis, 'fetch').mockImplementation(async (input, init) => {
    const url = String(input);
    if (url.endsWith(`/accounts/${personaId}/resume`) && init?.method === 'PATCH') {
      const ops = JSON.parse(String(init.body)) as { path: string; value: unknown }[];
      patches.push(...ops);
      const saved = ops.some((op) => op.path === '/status' && op.value === 'saved');
      const entry = saved
        ? { ...ACCOUNTS[personaId].entry, branch_id: 'E6', panel: 'E', messages: [], choices: [] }
        : null;
      return Response.json({ updates: [], entry });
    }
    if (url.endsWith(`/accounts/${personaId}/resume`)) {
      return Response.json(resume, { headers: { ETag: `"${resume.lock_version}"` } });
    }
    if (url.endsWith(`/accounts/${personaId}`)) return Response.json(ACCOUNTS[personaId]);
    return Response.json({ code: 'NOT_FOUND', message: '없는 경로예요.' }, { status: 404 });
  });
  return { spy, patches };
};

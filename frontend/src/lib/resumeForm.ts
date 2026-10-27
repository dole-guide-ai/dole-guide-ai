/**
 * 백엔드 이력서(`ResumeRead`, F-15)를 패널 A가 쓰는 예전 초안 모양(`ResumeDraftRead`)으로 바꾸는 임시 어댑터입니다.
 * 패널·모의 대화가 아직 예전 칸 이름(`competencies.careers`, `level` 등)을 써서 둔 것이며,
 * 화면을 새 API 타입으로 옮기면 지웁니다.
 * 백엔드는 칸마다 `{value, status, source, …}`이고 경로가 `/careers/c1/company_name`입니다.
 */

import type { components } from '@/types/api.gen';
import type { FieldStatus, FormUpdateEvent } from '@/types/chat.types';
import type { OccupationRef, ResumeDraftRead, ResumeFieldState } from '@/types/resume.types';

type ResumeRead = components['schemas']['ResumeRead'];
type FormField = components['schemas']['FormField'];
type Item = Record<string, unknown> & { item_id: string };

// 예전 칸 이름 ↔ 새 칸 이름 (학력만 다름)
const EDUCATION_RENAME: Record<string, string> = {
  education_level: 'level',
  is_highest_education: 'is_final',
};
const EDUCATION_BACK: Record<string, string> = { level: 'education_level' };

const isField = (node: unknown): node is FormField =>
  typeof node === 'object' && node !== null && 'status' in node && 'value' in node;

const metaOf = (f: FormField): ResumeFieldState => ({
  status: f.status as FieldStatus,
  source: f.source ?? undefined,
  transformed: f.transformed,
  evidence: (f.evidence ?? undefined) as ResumeFieldState['evidence'],
});

/** 항목 하나의 칸들을 값으로 풀고, 채워진 칸의 상태를 `{prefix}.{item_id}.{칸}`에 남깁니다. */
const unwrapItem = (
  item: Item,
  prefix: string,
  states: Record<string, ResumeFieldState>,
  rename: Record<string, string> = {},
) => {
  const out: Record<string, unknown> = { item_id: item.item_id };
  for (const [key, node] of Object.entries(item)) {
    if (!isField(node)) continue;
    const name = rename[key] ?? key;
    out[name] = node.value ?? null;
    if (node.status !== 'missing') states[`${prefix}.${item.item_id}.${name}`] = metaOf(node);
  }
  return out;
};

const unwrapGroup = (
  group: Record<string, unknown>,
  prefix: string,
  states: Record<string, ResumeFieldState>,
) => {
  const out: Record<string, unknown> = {};
  for (const [key, node] of Object.entries(group)) {
    if (!isField(node)) continue;
    out[key] = node.value ?? null;
    if (node.status !== 'missing') states[`${prefix}.${key}`] = metaOf(node);
  }
  return out;
};

const keep = (states: Record<string, ResumeFieldState>, path: string, f: FormField | undefined) => {
  if (f && f.status !== 'missing') states[path] = metaOf(f);
};

const experienceSummary = (item: Record<string, unknown> | undefined) => {
  if (!item?.experience_type) return null;
  if (item.experience_type === '신입') return '신입';
  const years = Number(item.experience_years ?? 0);
  const months = Number(item.experience_months ?? 0);
  return `경력 ${years}년 ${months}개월`;
};

export const resumeFromServer = (read: ResumeRead): ResumeDraftRead => {
  const states: Record<string, ResumeFieldState> = {};
  const data = read.data as unknown as Record<string, unknown>;
  const prefs = (data.job_preferences ?? {}) as Record<string, unknown>;

  const occupations = ((prefs.desired_occupations ?? []) as Item[]).map((o) =>
    unwrapItem(o, 'job_preferences.desired_occupations', states),
  );
  const first = occupations[0];
  const firstRaw = (prefs.desired_occupations as Item[] | undefined)?.[0];
  // 희망직종은 패널에서 한 줄이라 첫 직종의 칸 상태를 그 줄 칩으로 씁니다.
  keep(states, 'job_preferences.desired_occupations', firstRaw?.occupation as FormField);
  keep(states, 'job_preferences.experience_summary', firstRaw?.experience_type as FormField);
  keep(states, 'job_preferences.desired_duties', firstRaw?.desired_job_description as FormField);

  const prefValues = unwrapGroup(prefs, 'job_preferences', states);
  const regions = (prefValues.desired_regions ?? []) as { name: string }[];
  const competencies = unwrapGroup(
    (data.competencies ?? {}) as Record<string, unknown>,
    'competencies',
    states,
  );
  keep(states, 'competencies.certifications', data.certifications_status as FormField);
  keep(states, 'competencies.other_certifications', data.other_certifications as FormField);
  keep(states, 'resume_title', data.resume_title as FormField);

  const values = {
    schema_version: 'work24_resume_v2',
    status: read.status === 'saved' ? 'finalized' : 'draft',
    resume_title: ((data.resume_title as FormField | undefined)?.value as string) ?? null,
    education: ((data.education ?? []) as Item[]).map((e) =>
      unwrapItem(e, 'education', states, EDUCATION_RENAME),
    ),
    job_preferences: {
      ...prefValues,
      desired_occupations: occupations
        .map((o) => o.occupation as OccupationRef | null)
        .filter((o): o is OccupationRef => !!o),
      experience_summary: experienceSummary(first),
      desired_duties: (first?.desired_job_description as string) ?? null,
      desired_regions: regions.map((r) => r.name),
      work_arrangements: prefValues.work_arrangements ?? [],
      search_keywords: prefValues.search_keywords ?? [],
    },
    competencies: {
      ...competencies,
      careers: ((data.careers ?? []) as Item[]).map((c) =>
        unwrapItem(c, 'competencies.careers', states),
      ),
      certifications: ((data.certifications ?? []) as Item[]).map((c) =>
        unwrapItem(c, 'competencies.certifications', states),
      ),
      other_certifications:
        ((data.other_certifications as FormField | undefined)?.value as string[]) ?? [],
    },
    additional_info: unwrapGroup(
      (data.additional_info ?? {}) as Record<string, unknown>,
      'additional_info',
      states,
    ),
    enabled_sections: [],
  };

  return {
    ...(values as unknown as Omit<ResumeDraftRead, 'field_states' | 'completeness'>),
    field_states: states,
    completeness: {
      done: read.completeness.filled,
      total: read.completeness.total ?? 5,
      sections: read.completeness.sections ?? {},
    },
    required_paths: read.required_paths ?? [],
    next_question: read.next_question ?? null,
    can_save: read.can_save,
    lock_version: read.lock_version,
    profile_display: read.profile_display,
  };
};

/**
 * 패널의 직접 고치기(예전 점 경로)를 백엔드 JSON Patch 한 줄로 바꿉니다.
 * 새 구조에 같은 칸이 없으면(경력여부 요약·희망직무내용) null이라 대화로 고칩니다.
 */
export const resumePatchOp = (path: string, value: unknown) => {
  if (path === 'education' && Array.isArray(value)) {
    const first = value[0] as { item_id: string; level: string };
    return {
      op: 'replace',
      path: `/education/${first.item_id}/education_level`,
      value: first.level,
    };
  }
  const parts = path.split('.');
  if (parts[0] === 'competencies' && (parts[1] === 'careers' || parts[1] === 'certifications')) {
    parts.shift();
  } else if (path === 'competencies.other_certifications') {
    parts.shift();
  } else if (
    path === 'job_preferences.experience_summary' ||
    path === 'job_preferences.desired_duties'
  ) {
    return null;
  }
  if (parts[0] === 'education' && parts.length === 3)
    parts[2] = EDUCATION_BACK[parts[2]] ?? parts[2];
  return { op: 'replace', path: `/${parts.join('/')}`, value };
};

// 패널이 `competencies` 아래에 두는 백엔드 최상위 칸
const UNDER_COMPETENCIES = new Set(['careers', 'certifications', 'other_certifications']);

/**
 * 대화의 이력서 `form_update`(백엔드 경로 `/careers/c1/company_name`)를 패널의 예전 경로
 * (`/competencies/careers/c1/company_name`)로 바꿉니다. 처음 불러올 때 `resumeFromServer`가 하는
 * 변환과 같아야 대화 중에 패널이 바로 바뀝니다.
 */
export const resumeUpdateFromServer = (event: FormUpdateEvent): FormUpdateEvent => {
  if (!event.path.startsWith('/')) return event;
  const parts = event.path.slice(1).split('/');
  let { value } = event;
  if (parts[0] === 'certifications_status') {
    // 패널에는 "자격증 없음" 상태 칩만 있습니다. 값을 넣으면 자격증 목록을 덮어씁니다.
    return { ...event, path: '/competencies/certifications', value: undefined };
  }
  if (UNDER_COMPETENCIES.has(parts[0])) parts.unshift('competencies');
  if (parts[0] === 'education' && parts.length === 3) {
    parts[2] = EDUCATION_RENAME[parts[2]] ?? parts[2];
  }
  if (event.path === '/job_preferences/desired_regions' && Array.isArray(value)) {
    value = value.map((r) => (typeof r === 'object' && r && 'name' in r ? r.name : r));
  }
  return { ...event, path: `/${parts.join('/')}`, value };
};

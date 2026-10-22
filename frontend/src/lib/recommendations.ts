/**
 * 백엔드 부족한 활동 추천(`RecommendationList`, F-19)을 추천 상자가 쓰는 모양(`RecommendationsRead`)으로 바꾸는
 * 임시 어댑터입니다. 추천 상자가 아직 예전 추천 구조를 쓰고 있어서 둔 것이며, 화면을 새 API 타입으로 옮기면 지웁니다.
 */

import type { components } from '@/types/api.gen';
import type { RecommendationsRead } from '@/types/procedure.types';

type RecommendationList = components['schemas']['RecommendationList'];

/** 공고 추천은 하지 않습니다 (2-2.8, MVP 제외). */
const NOTE = '공고는 고용24 채용정보에서 직접 골라 주세요.';

export const recommendationsFromServer = (list: RecommendationList): RecommendationsRead => ({
  items: list.items.map((item) => ({
    recommendation_id: item.recommendation_id,
    title: item.title,
    detail: item.evidence_hint ? `필요 증빙: ${item.evidence_hint}` : '따로 낼 증빙이 없어요.',
    kind: item.category === 'job_search' ? 'job_search' : 'other',
    evidence_label: item.evidence_hint ? '증빙 필요' : '증빙 불필요',
    limit_text: item.reason.split(' · ').find((part) => part.startsWith('한도')) ?? null,
    rule_refs: ((item.external?.rule_refs as string[] | undefined) ?? []).slice(),
  })),
  deadline_text: list.deadline_text,
  note: NOTE,
  cite: list.cite ?? '',
});

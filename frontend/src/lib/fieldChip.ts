import type { ChipTone } from '@/components/Chip';

import type { FieldMeta } from '@/lib/formStore';

export interface ChipSpec {
  label: string;
  tone: ChipTone;
}

interface FieldChipOptions {
  /** 본인 답변 필수 칸(2-3 근로·소득)이면 비어 있을 때 `답변 필요`. */
  isSelfAnswerRequired?: boolean;
}

/** 저장 상태 6종 + 출처 + transformed → 칩 12종 (상세기획 2-0.6 표). */
export const fieldChip = (meta?: FieldMeta, options: FieldChipOptions = {}): ChipSpec => {
  if (!meta || meta.status === 'missing' || meta.status === 'rejected') {
    return options.isSelfAnswerRequired
      ? { label: '답변 필요', tone: 'warn' }
      : { label: '아직 없음', tone: 'neutral' };
  }

  if (meta.status === 'conflict' || (meta.status === 'extracted' && meta.transformed)) {
    return { label: '확인 필요', tone: 'warn' };
  }

  if (meta.status === 'not_applicable') return { label: '해당 없음', tone: 'neutral' };

  if (meta.status === 'extracted') {
    if (meta.source === 'seed') return { label: '예전 이력서', tone: 'info' };
    if (meta.source === 'work24_import') return { label: '고용24 불러오기', tone: 'info' };
    return { label: '문서에서 확인', tone: 'info' };
  }

  // confirmed
  switch (meta.source) {
    case 'user_answer':
      // 같은 출처라도 신청서 본인 답변 칸이면 `본인 확인`, 그 밖은 `대화로 추가`
      return options.isSelfAnswerRequired
        ? { label: '본인 확인', tone: 'ok' }
        : { label: '대화로 추가', tone: 'ok' };
    case 'direct':
      return { label: '직접 입력', tone: 'ok' };
    case 'auto':
      return { label: '자동', tone: 'neutral' };
    case 'account':
      return { label: '고용24에서', tone: 'neutral' };
    case 'doc':
      return { label: '문서에서 확인', tone: 'info' };
    case 'seed':
      return { label: '예전 이력서', tone: 'info' };
    case 'work24_import':
      return { label: '고용24 불러오기', tone: 'info' };
    default:
      return { label: '대화로 추가', tone: 'ok' };
  }
};

/** 확정되지 않아 완성도에 넣지 않는 칸인지 (`확인 필요`). */
export const needsCheck = (meta?: FieldMeta) =>
  !!meta && (meta.status === 'conflict' || (meta.status === 'extracted' && !!meta.transformed));

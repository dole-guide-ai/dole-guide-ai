'use client';

import { Button } from '@/components/Button';
import { EvidenceLine } from '@/components/EvidenceLine';
import { JobSearchCard } from '@/features/recognition/JobSearchCard';
import { OtherActivityCard } from '@/features/recognition/OtherActivityCard';
import { EXCLUDED_REASON_LABEL, yesNo } from '@/features/recognition/recognitionLabels';
import { SubmitBox } from '@/features/recognition/SubmitBox';
import { useConfirmRecognition } from '@/features/recognition/useConfirmRecognition';
import { useRecognitionDraft } from '@/features/recognition/useRecognitionDraft';
import { useRecognitionForm } from '@/features/recognition/useRecognitionForm';
import { FieldRow } from '@/features/resume/FieldRow';
import { ResumeSection } from '@/features/resume/ResumeSection';

import { ApiError } from '@/lib/api';
import { formatDotDate, formatShortDate } from '@/lib/dateFormat';
import { type ChipSpec, fieldChip } from '@/lib/fieldChip';
import type { FieldMeta } from '@/lib/formStore';
import type { SessionRead } from '@/types/demo.types';
import type { ConsentValue, RecognitionFormRead } from '@/types/recognition.types';

/**
 * 패널 C 실업인정 신청서 검토 (2-3.2): 고용24 화면 순서(사전 확인 → 1 실업인정 정보등록 → 2 재취업 활동정보등록
 * → 제출)로 보여 줍니다. 본인 답변 칸은 패널에서 고치지 않고 대화 질문으로만 받습니다 (2-0.6).
 */
interface RecognitionPanelProps {
  session: SessionRead;
  /** `활동 다시 보기`: 패널 B로 돌아갑니다. */
  onBackToRound?: () => void;
  /** 모의 제출·출석 준비 확인이 끝나면 다음 안내를 이어 가도록 대화로 알립니다. */
  onConfirmed?: (mode: 'send' | 'attend') => void;
}

const WORK24_CHIP: ChipSpec = { label: '고용24에서', tone: 'neutral' };
const OPTIONAL_CHIP: ChipSpec = { label: '선택', tone: 'neutral' };

const CONSENT_LABEL: Record<ConsentValue, string> = {
  agree: '동의함',
  disagree: '동의하지 않음',
  decide_on_work24: '고용24에서 고르기',
};

/** 본인 답변 칸 칩: 답하기 전 `답변 필요`, 답한 뒤 `본인 확인 · 12.16` (2-3.3). */
const selfChip = (meta: FieldMeta | undefined, answeredOn: string | null | undefined) => {
  const spec = fieldChip(meta, { isSelfAnswerRequired: true });
  return spec.label === '본인 확인' && answeredOn
    ? { ...spec, label: `본인 확인 · ${formatDotDate(answeredOn)}` }
    : spec;
};

export const RecognitionPanel = ({
  session,
  onBackToRound,
  onConfirmed,
}: RecognitionPanelProps) => {
  const query = useRecognitionForm(session.session_id, session.derived.current_round);
  const draft = useRecognitionDraft();
  const confirm = useConfirmRecognition();

  if (query.isPending) return <p className="text-muted text-base">신청서를 정리하는 중…</p>;
  if (query.isError) {
    return (
      <p role="alert" className="text-danger text-base">
        {query.error instanceof ApiError ? query.error.message : '신청서를 불러오지 못했어요.'}
      </p>
    );
  }

  // 저장소가 아직 채워지기 전(첫 렌더)에는 받은 응답을 그대로 씁니다.
  const form = { ...query.data, ...draft.values } as RecognitionFormRead;
  const fields = { ...query.data.field_states, ...draft.fields };
  const info = form.recognition_info;
  const credit = form.unemployment_credit;
  const work = form.work_and_employment;
  const activity = form.reemployment_activity;
  const plan = form.notification_and_plan;
  const shortBy = activity.required.activities - activity.counted.activities;
  const prevChip = (path: string, answeredOn?: string | null) => selfChip(fields[path], answeredOn);
  const workPath = (key: string) => `work_and_employment.${key}`;

  const handleSubmit = () => {
    const mode = form.submit_mode === 'attend' ? 'attend' : 'send';
    confirm.mutate({ submit_mode: mode }, { onSuccess: () => onConfirmed?.(mode) });
  };

  return (
    <div className="flex flex-col gap-4">
      <p className="bg-canvas text-muted rounded-xl px-4 py-2 text-sm">
        사전 확인 · 재취업을 위한 약속, 부정수급 고지 확인서는 고용24에서 본인이 확인해요.
      </p>

      <ResumeSection title="1 실업인정 정보등록">
        <FieldRow
          label="신청 정보"
          value={`${form.recognition_round}차 · ${formatShortDate(info.recognition_date)}${
            info.attendance_round ? ' · 고용센터 출석' : ''
          }`}
          meta={fields.recognition_info}
        />
        <FieldRow
          label="대상 기간"
          value={`${formatDotDate(info.period_start)} ~ ${formatDotDate(info.period_end)}`}
          meta={fields.recognition_info}
        />
        <FieldRow
          label="지급계좌"
          value="이전에 받은 계좌가 기본으로 들어가요"
          chip={WORK24_CHIP}
        />
        <FieldRow
          label="실업크레딧"
          value={
            credit.is_applicable
              ? [
                  credit.credit_application_choice,
                  credit.notice_delivery_method,
                  credit.automatic_payment_choice && `자동이체 ${credit.automatic_payment_choice}`,
                  credit.income_asset_consent && `재산 소득 확인 ${credit.income_asset_consent}`,
                ]
                  .filter(Boolean)
                  .join(' · ')
              : null
          }
          chip={
            credit.is_applicable
              ? prevChip('unemployment_credit', credit.answered_on)
              : { label: '해당 없음', tone: 'neutral' }
          }
        />
        <FieldRow
          label="근로·노무제공"
          value={yesNo(work.has_work_or_service)}
          isRequired
          chip={prevChip(workPath('has_work_or_service'), work.answered_on)}
        />
        {work.has_work_or_service && (
          <div className="bg-canvas my-1 rounded-xl px-3 py-1">
            <FieldRow
              label="근로내역(일한 날)"
              value={work.work_details?.work_dates}
              isRequired
              chip={prevChip(workPath('work_details.work_dates'), work.answered_on)}
            />
            <FieldRow
              label="총 근로시간"
              value={
                work.work_details?.total_hours != null
                  ? `${work.work_details.total_hours}시간`
                  : null
              }
              isRequired
              chip={prevChip(workPath('work_details.total_hours'), work.answered_on)}
            />
            <FieldRow
              label="소득수령(예정)일"
              value={
                work.work_details?.income_date
                  ? formatShortDate(work.work_details.income_date)
                  : null
              }
              isRequired
              chip={prevChip(workPath('work_details.income_date'), work.answered_on)}
            />
            <FieldRow
              label="소득수령(예정)액"
              value={
                work.work_details?.income_amount != null
                  ? `${work.work_details.income_amount.toLocaleString('ko-KR')}원`
                  : null
              }
              isRequired
              chip={prevChip(workPath('work_details.income_amount'), work.answered_on)}
            />
            <p className="text-muted py-1 text-sm">
              일한 날은 신청서에 꼭 적어야 해요. 일한 시간이 길면 취업으로 볼 수도 있어요.
              고용센터에 확인해 주세요.
            </p>
          </div>
        )}
        <FieldRow
          label="취업·개인 사업"
          value={yesNo(work.has_employment)}
          isRequired
          chip={prevChip(workPath('has_employment'), work.answered_on)}
        />
        <FieldRow
          label="산재 휴업급여"
          value={yesNo(work.has_industrial_accident_benefit_right)}
          isRequired
          chip={prevChip(workPath('has_industrial_accident_benefit_right'), work.answered_on)}
        />
      </ResumeSection>

      {form.locked_reason ? (
        <p role="alert" className="bg-warn-soft text-warn rounded-xl px-4 py-3 text-base">
          {form.locked_reason === 'employment'
            ? '취업·개인 사업이 있으면 실업인정일 전에 관할 고용센터에 먼저 문의해 주세요. 신청서 작성은 여기서 멈춰요.'
            : '산재 휴업급여 수급권이 있으면 인터넷으로 신청할 수 없어요. 관할 고용센터에 문의해 주세요.'}
        </p>
      ) : (
        <>
          <section className="flex flex-col gap-3" aria-label="2 재취업 활동정보등록">
            <h3 className="text-base font-bold">2 재취업 활동정보등록</h3>
            <p className="bg-brand-soft text-brand rounded-xl px-4 py-2 text-sm">
              {form.recognition_round}차 실업인정 필수 등록 요건: 재취업활동{' '}
              {activity.required.activities}회 등록 대상
              {activity.required.job_search > 0 &&
                `, 구직활동 ${activity.required.job_search}회 이상 포함`}
            </p>
            {shortBy > 0 && (
              <div className="bg-warn-soft flex flex-wrap items-center justify-between gap-2 rounded-xl px-4 py-3">
                <p className="text-warn text-base font-semibold">
                  필요 활동이 {shortBy}건 부족해요. 제출은 막지 않지만 인정되지 않을 수 있어요.
                </p>
                {onBackToRound && (
                  <Button variant="secondary" onClick={onBackToRound}>
                    활동 다시 보기
                  </Button>
                )}
              </div>
            )}
            {activity.job_search_activities.map((item) => (
              <JobSearchCard
                key={item.item_id}
                activity={item}
                meta={fields[`reemployment_activity.job_search_activities.${item.item_id}`]}
              />
            ))}
            {activity.excluded.length > 0 && (
              <details className="text-muted text-sm">
                <summary className="cursor-pointer">
                  참고 · 계산에서 뺀 활동 {activity.excluded.length}건 (신청서에 넣지 않아요)
                </summary>
                <ul className="mt-1 pl-4">
                  {activity.excluded.map((item) => (
                    <li key={item.item_id}>
                      {formatShortDate(item.activity_date)} {item.company_name} ·{' '}
                      {EXCLUDED_REASON_LABEL[item.reason]}
                    </li>
                  ))}
                </ul>
              </details>
            )}
            {activity.has_other_reemployment_activity ? (
              activity.other_reemployment_activities.map((item) => (
                <OtherActivityCard key={item.item_id} activity={item} />
              ))
            ) : (
              <p className="text-muted text-sm">구직활동 외 활동사항 · 없음</p>
            )}
          </section>

          <ResumeSection title="통지방법 · 다음 활동">
            <FieldRow
              label="지급 결정 통지"
              value={plan.payment_notification_method}
              isRequired
              chip={prevChip('notification_and_plan.payment_notification_method')}
            />
            <FieldRow
              label="재취업희망 유형"
              value={
                plan.desired_reemployment_type.length
                  ? plan.desired_reemployment_type.join(', ')
                  : '고르지 않으면 이전 일자리 유형이 적용돼요'
              }
              meta={fields['notification_and_plan.desired_reemployment_type']}
            />
            <FieldRow
              label="다음 출석일까지 활동"
              value={
                plan.next_activity.value &&
                [plan.next_activity.value, plan.next_activity.memo].filter(Boolean).join(' · ')
              }
              isRequired
              chip={prevChip('notification_and_plan.next_activity', plan.next_activity.answered_on)}
            />
            <FieldRow
              label="개인정보 이용 동의"
              value={
                form.personal_information_consent.value &&
                CONSENT_LABEL[form.personal_information_consent.value]
              }
              chip={
                form.personal_information_consent.value
                  ? prevChip(
                      'personal_information_consent',
                      form.personal_information_consent.answered_on,
                    )
                  : OPTIONAL_CHIP
              }
            />
          </ResumeSection>

          <SubmitBox
            key={form.recognition_round}
            mode={form.submit_mode}
            recognitionDate={info.recognition_date}
            checklist={form.checklist}
            attendItems={form.attend_items}
            canSubmit={form.can_submit}
            isSubmitting={confirm.isPending}
            isDone={form.mock_submission !== null}
            onSubmit={handleSubmit}
          />
          {confirm.isError && (
            <p role="alert" className="text-danger text-sm">
              {confirm.error instanceof ApiError ? confirm.error.message : '확인하지 못했어요.'}
            </p>
          )}
        </>
      )}

      <div className="flex flex-col gap-1">
        <p className="text-muted text-sm">
          실업인정은 본인이 직접 신청해요. 서비스는 정리·점검만 하고 최종 인정 여부는 관할
          고용센터가 판단해요.
        </p>
        <EvidenceLine cite={form.cite} />
      </div>
    </div>
  );
};

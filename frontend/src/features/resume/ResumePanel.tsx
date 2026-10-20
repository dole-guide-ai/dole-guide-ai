'use client';

import { Button } from '@/components/Button';
import { FieldRow } from '@/features/resume/FieldRow';
import {
  formatPeriod,
  formatYm,
  OPTIONAL_SECTIONS,
  QUESTION_LABEL,
} from '@/features/resume/resumeLabels';
import { ResumeSection } from '@/features/resume/ResumeSection';
import { useConfirmResume } from '@/features/resume/useConfirmResume';
import { usePatchResumeField } from '@/features/resume/usePatchResumeField';
import { useResumeDraft } from '@/features/resume/useResumeDraft';
import { useResumeForm } from '@/features/resume/useResumeForm';

import { ApiError } from '@/lib/api';
import { needsCheck } from '@/lib/fieldChip';
import type { FieldMeta } from '@/lib/formStore';
import type { SessionRead } from '@/types/demo.types';
import type { ResumeCompetencies } from '@/types/resume.types';

/**
 * 패널 A: 고용24 이력서 항목을 같은 순서로 보여 주고, 완성도(꼭 묻는 5개)와 저장 버튼을 둡니다 (2-1.2 · 2-1.6).
 * 값·칩은 양식 저장소에서 읽고, 완성도·저장 가능 여부는 서버 값을 그대로 씁니다 (계산은 백엔드).
 * 글자 칸은 `직접 입력`으로 패널에서 바로 고칠 수 있습니다 (2-0.6, 본인 답변 칸 제외).
 */
interface ResumePanelProps {
  session: SessionRead;
  onEditRequest?: (label: string) => void;
  /** 완료한 단계를 다시 볼 때(1.8): 저장·고치기·직접 입력을 숨깁니다. */
  isReadOnly?: boolean;
}

const WORK24_CHIP = { label: '고용24에서', tone: 'neutral' } as const;
const OPTIONAL_CHIP = { label: '있으면', tone: 'neutral' } as const;

const hasCheck = (fields: Record<string, FieldMeta>, prefix: string) =>
  Object.entries(fields).some(([path, meta]) => path.startsWith(prefix) && needsCheck(meta));

const listText = (items: string[] | undefined) => (items?.length ? items.join(', ') : null);

/** 그 밖의 보유역량 한 영역의 값 (불러오기·대화로 들어온 항목 이름). 비어 있으면 null. */
const sectionText = (section: unknown) => {
  if (!Array.isArray(section) || section.length === 0) return null;
  return section
    .map((item) =>
      typeof item === 'object' && item && 'name' in item ? String(item.name) : String(item),
    )
    .join(', ');
};

export const ResumePanel = ({ session, onEditRequest, isReadOnly = false }: ResumePanelProps) => {
  const query = useResumeForm(session.session_id);
  const { values, fields, completeness } = useResumeDraft();
  const confirm = useConfirmResume();
  const patch = usePatchResumeField();

  if (query.isPending) return <p className="text-muted text-base">이력서를 불러오는 중…</p>;
  if (query.isError) {
    const message =
      query.error instanceof ApiError ? query.error.message : '이력서를 불러오지 못했어요.';
    return (
      <p role="alert" className="text-danger text-base">
        {message}
      </p>
    );
  }

  const edit = (label: string) =>
    onEditRequest && !isReadOnly ? () => onEditRequest(label) : undefined;
  const direct = (path: string) =>
    isReadOnly ? undefined : (value: string) => patch.mutateAsync({ path, op: 'set', value });
  const education = values.education ?? [];
  const prefs = values.job_preferences;
  const careers = values.competencies?.careers ?? [];
  const certifications = values.competencies?.certifications ?? [];
  const certMeta = fields['competencies.certifications'];
  const isCertNone = certMeta?.status === 'not_applicable';
  const salary = prefs?.desired_salary;
  const salaryText = salary?.negotiable
    ? '면접 후 결정'
    : salary?.amount
      ? `월 ${salary.amount}만원 이상`
      : null;

  const done = {
    title: !!values.resume_title && !needsCheck(fields.resume_title),
    education: education.some((e) => e.level && e.school_name) && !hasCheck(fields, 'education'),
    prefs:
      !!prefs?.desired_occupations?.length &&
      !!prefs.desired_regions?.length &&
      !!salaryText &&
      !!prefs.employment_contract_type &&
      !hasCheck(fields, 'job_preferences'),
    careers:
      careers.some((c) => c.company_name && c.start_date && c.end_date && c.position) &&
      !hasCheck(fields, 'competencies.careers'),
    certifications:
      (isCertNone || certifications.some((c) => c.certificate_name)) &&
      !hasCheck(fields, 'competencies.certifications'),
  };

  const isUpdate = session.entry.branch_id === 'E7b';
  const saveLabel = isUpdate ? '확인하고 이력서 최신화' : '확인하고 이력서 저장';
  const canSave = values.can_save === true && !confirm.isPending;
  const nextQuestion = values.next_question ? QUESTION_LABEL[values.next_question] : null;

  return (
    <div className="flex flex-col gap-4">
      <div className="bg-canvas flex flex-wrap items-center justify-between gap-3 rounded-xl px-4 py-3">
        <div>
          <p className="text-muted text-sm">완성도 (꼭 묻는 5개)</p>
          <p className="text-2xl font-bold" aria-label="완성도">
            {completeness?.done ?? 0} / {completeness?.total ?? 5}
          </p>
        </div>
        {!isReadOnly && (
          <div className="flex flex-col items-end gap-1">
            <Button onClick={() => confirm.mutate()} disabled={!canSave}>
              {confirm.isPending ? '저장하는 중…' : saveLabel}
            </Button>
            {!canSave && (
              <span className="text-muted text-xs">
                필수 항목을 다 채우고 확인 필요가 없어야 해요
              </span>
            )}
          </div>
        )}
      </div>
      {confirm.isError && (
        <p role="alert" className="text-danger text-sm">
          {confirm.error instanceof ApiError ? confirm.error.message : '저장하지 못했어요.'}
        </p>
      )}

      <ResumeSection title="이력서 제목" isRequired isDone={done.title}>
        <FieldRow
          label="제목"
          value={values.resume_title}
          rawValue={values.resume_title}
          meta={fields.resume_title}
          isRequired
          onEdit={edit('이력서 제목')}
          onDirectSave={direct('resume_title')}
        />
      </ResumeSection>

      <ResumeSection title="기본정보" hint="고용24 회원정보에서 자동으로 들어가요">
        <FieldRow label="성명·연락처·주소" value="고용24 회원정보에서 자동" chip={WORK24_CHIP} />
      </ResumeSection>

      <ResumeSection title="학력사항" isRequired isDone={done.education}>
        {education.length === 0 && <FieldRow label="학력" isRequired onEdit={edit('학력')} />}
        {education.map((item) => (
          <FieldRow
            key={item.item_id}
            label={item.level ?? '학력'}
            value={[
              item.school_name,
              item.graduation_status,
              formatPeriod(item.start_date, item.end_date),
            ]
              .filter(Boolean)
              .join(' · ')}
            rawValue={item.school_name}
            meta={
              fields[`education.${item.item_id}.school_name`] ??
              fields[`education.${item.item_id}.level`]
            }
            isRequired
            onEdit={edit('학력')}
            onDirectSave={direct(`education.${item.item_id}.school_name`)}
          />
        ))}
      </ResumeSection>

      <ResumeSection title="희망조건" isRequired isDone={done.prefs}>
        <FieldRow
          label="희망직종"
          value={listText(prefs?.desired_occupations?.map((o) => o.name))}
          meta={fields['job_preferences.desired_occupations']}
          isRequired
          onEdit={edit('희망 직종')}
        />
        <FieldRow
          label="희망근무지역"
          value={listText(prefs?.desired_regions)}
          meta={fields['job_preferences.desired_regions']}
          isRequired
          onEdit={edit('희망 근무지역')}
        />
        <FieldRow
          label="희망임금"
          value={salaryText}
          meta={fields['job_preferences.desired_salary']}
          isRequired
          onEdit={edit('희망 임금')}
        />
        <FieldRow
          label="고용형태"
          value={prefs?.employment_contract_type}
          meta={fields['job_preferences.employment_contract_type']}
          isRequired
          onEdit={edit('고용형태')}
        />
        <FieldRow
          label="병역대체"
          value={prefs?.military_alternative}
          meta={fields['job_preferences.military_alternative']}
          isRequired
        />
      </ResumeSection>

      <ResumeSection title="보유역량 · 경력사항" isRequired isDone={done.careers}>
        {careers.length === 0 && <FieldRow label="회사명" isRequired onEdit={edit('경력')} />}
        {careers.map((career) => {
          const base = `competencies.careers.${career.item_id}`;
          const name = career.company_name ?? '경력';
          return (
            <div key={career.item_id} className="py-1">
              <FieldRow
                label="회사명"
                value={career.company_name}
                rawValue={career.company_name}
                meta={fields[`${base}.company_name`]}
                isRequired
                onEdit={edit(`${name} 회사명`)}
                onDirectSave={direct(`${base}.company_name`)}
              />
              <FieldRow
                label="재직기간"
                value={formatPeriod(career.start_date, career.end_date)}
                meta={fields[`${base}.end_date`] ?? fields[`${base}.start_date`]}
                isRequired
                onEdit={edit(`${name} 재직기간`)}
              />
              <FieldRow
                label="직급/직책"
                value={career.position}
                rawValue={career.position}
                meta={fields[`${base}.position`]}
                isRequired
                onEdit={edit(`${name} 직급`)}
                onDirectSave={direct(`${base}.position`)}
              />
              <FieldRow
                label="재직여부"
                value={career.employment_status}
                meta={fields[`${base}.employment_status`]}
                isRequired
              />
              <FieldRow
                label="주요 직무"
                value={career.main_duties}
                rawValue={career.main_duties}
                meta={fields[`${base}.main_duties`]}
                onEdit={edit(`${name} 주요 직무`)}
                onDirectSave={direct(`${base}.main_duties`)}
              />
            </div>
          );
        })}
      </ResumeSection>

      <ResumeSection title="보유역량 · 보유 자격면허" isRequired isDone={done.certifications}>
        {certifications.length === 0 && (
          <FieldRow label="자격면허" meta={certMeta} isRequired onEdit={edit('자격증')} />
        )}
        {certifications.map((cert) => {
          const base = `competencies.certifications.${cert.item_id}`;
          return (
            <FieldRow
              key={cert.item_id}
              label="자격면허"
              value={[
                cert.certificate_name,
                cert.issuing_organization,
                formatYm(cert.acquired_date),
              ]
                .filter(Boolean)
                .join(' · ')}
              meta={fields[`${base}.certificate_name`]}
              isRequired
              onEdit={edit(`${cert.certificate_name ?? '자격증'}`)}
            />
          );
        })}
      </ResumeSection>

      <ResumeSection title="그 밖의 보유역량" hint="있으면 말해 주세요">
        {OPTIONAL_SECTIONS.map(({ key, label }) => (
          <FieldRow
            key={key}
            label={label}
            value={sectionText(values.competencies?.[key as keyof ResumeCompetencies])}
            meta={fields[`competencies.${key}`]}
            chip={fields[`competencies.${key}`] ? undefined : OPTIONAL_CHIP}
          />
        ))}
        <FieldRow
          label="직무능력"
          value="고용24에서 직무능력 자동 추천으로 골라요"
          chip={WORK24_CHIP}
        />
      </ResumeSection>

      <ResumeSection title="운전 및 차량소유">
        <FieldRow
          label="운전가능"
          value={
            values.additional_info?.can_drive == null
              ? null
              : values.additional_info.can_drive
                ? '예'
                : '아니오'
          }
          meta={fields['additional_info.can_drive']}
        />
      </ResumeSection>

      {nextQuestion && !isReadOnly && (
        <p className="bg-brand-soft text-brand rounded-xl px-4 py-2 text-sm">
          AI가 이어서 물어볼 것 · {nextQuestion}
        </p>
      )}
    </div>
  );
};

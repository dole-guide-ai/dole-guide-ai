'use client';

import { Button } from '@/components/Button';
import { FieldRow } from '@/features/resume/FieldRow';
import {
  CONTRACT_TYPES,
  EDUCATION_LEVELS,
  EMPLOYMENT_STATUSES,
  formatPeriod,
  formatYm,
  gpaText,
  GRADUATION_STATUSES,
  isCollegeLevel,
  MILITARY_OPTIONS,
  occupationText,
  OPTIONAL_SECTIONS,
  QUESTION_LABEL,
  splitPeriod,
  YES_NO,
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
import type { ResumeCompetencies, ResumeEducation } from '@/types/resume.types';

/**
 * 패널 A: 고용24 이력서 항목을 같은 순서로 보여 주고, 완성도(꼭 묻는 5개)와 저장 버튼을 둡니다 (2-1.2 · 2-1.6).
 * 값·칩은 양식 저장소에서 읽고, 완성도·저장 가능 여부는 서버 값을 그대로 씁니다 (계산은 백엔드).
 * 공통코드가 필요한 칸(희망직종·희망지역·직종)을 빼고는 `직접 입력`으로 패널에서 바로 고칠 수 있습니다
 * (2-0.6, 시연 개선 8번). 선택형 칸은 고용24 선택지에서 고릅니다.
 */
interface ResumePanelProps {
  session: SessionRead;
  onEditRequest?: (label: string) => void;
  /** 완료한 단계를 다시 볼 때(1.8): 저장·고치기·직접 입력을 숨깁니다. */
  isReadOnly?: boolean;
  /** 저장한 이력서를 다시 고칠 때(2-1.6): 버튼 이름 `다시 저장하기` */
  saveLabel?: string;
  onSaved?: () => void;
}

const WORK24_CHIP = { label: '고용24에서', tone: 'neutral' } as const;
// 고르지 않아도 되는 칸 (시연 개선 9번: '있으면' → '선택')
const OPTIONAL_CHIP = { label: '선택', tone: 'neutral' } as const;

const hasCheck = (fields: Record<string, FieldMeta>, prefix: string) =>
  Object.entries(fields).some(([path, meta]) => path.startsWith(prefix) && needsCheck(meta));

const listText = (items: string[] | undefined) => (items?.length ? items.join(', ') : null);

const yesNoText = (value: boolean | null | undefined) =>
  value === null || value === undefined ? null : value ? '예' : '아니오';

/** 직접 입력 글을 저장 값으로 바꿉니다 (시연 개선 8번). 형식 검사는 서버 값 정리가 합니다. */
const toList = (text: string) =>
  text
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean);

const toYesNo = (text: string) => text === '예';

const toMonthlyWage = (text: string) => ({
  amount: Number(text),
  unit: 'monthly',
  negotiable: false,
});

const firstEducation = (level: string): ResumeEducation[] => [
  {
    item_id: 'edu_001',
    level,
    graduation_status: null,
    school_name: null,
    start_date: null,
    end_date: null,
    is_final: true,
  },
];

const periodRaw = (start: string | null | undefined, end: string | null | undefined) =>
  start || end ? `${start ?? ''} ~ ${end ?? ''}` : null;

/**
 * AI가 물어볼 순서 (2-1.3 `next_resume_question` 순서): 서버가 준 남은 질문 목록에서 지금 질문부터 보여 줍니다.
 * 목록이 없으면 지금 질문 하나만.
 */
const questionQueue = (next: string | null | undefined, queue: string[] | undefined) => {
  if (!next) return [];
  const ids = queue?.length ? queue : [next];
  const start = ids.indexOf(next);
  const ordered = start === -1 ? [next, ...ids] : ids.slice(start);
  return ordered.map((id) => QUESTION_LABEL[id]).filter(Boolean);
};

/**
 * 그 밖의 보유역량 한 영역의 값 (불러오기·대화로 들어온 항목 이름). 비어 있으면 null.
 * 컴퓨터 활용만 배열이 아니라 `{ selected_skills, other_skills }` 객체입니다 (데이터 설계 3.11).
 */
const sectionText = (section: unknown) => {
  if (section && typeof section === 'object' && 'selected_skills' in section) {
    const { selected_skills, other_skills } = section as ResumeCompetencies['computer_skills'];
    const parts = [...(selected_skills ?? []), other_skills].filter(Boolean);
    return parts.length ? parts.join(', ') : null;
  }
  if (!Array.isArray(section) || section.length === 0) return null;
  return section
    .map((item) =>
      typeof item === 'object' && item && 'name' in item ? String(item.name) : String(item),
    )
    .join(', ');
};

export const ResumePanel = ({
  session,
  onEditRequest,
  isReadOnly = false,
  saveLabel: saveLabelOverride,
  onSaved,
}: ResumePanelProps) => {
  const query = useResumeForm(session.session_id, session.persona_id);
  const { values, fields, completeness } = useResumeDraft();
  const confirm = useConfirmResume(session.persona_id);
  const patch = usePatchResumeField(session.session_id, session.persona_id);

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
  const direct = (path: string, toValue: (text: string) => unknown = (text) => text) =>
    isReadOnly
      ? undefined
      : (text: string) => patch.mutateAsync({ path, op: 'set', value: toValue(text) });
  /** 기간은 한 칸에 '시작 ~ 끝'으로 적고, 시작·끝을 한 PATCH로 고칩니다(버전이 한 번만 바뀜). */
  const directPeriod = (base: string) =>
    isReadOnly
      ? undefined
      : async (text: string) => {
          const { start, end } = splitPeriod(text);
          await patch.mutateAsync([
            { path: `${base}.start_date`, op: 'set', value: start },
            { path: `${base}.end_date`, op: 'set', value: end },
          ]);
        };
  const profile = values.profile_display;
  const education = values.education ?? [];
  const prefs = values.job_preferences;
  const careers = values.competencies?.careers ?? [];
  const certifications = values.competencies?.certifications ?? [];
  // 고용24에서 조회되지 않는 민간등록자격 등은 기타자격으로 따로 둡니다 (데이터 설계 3.9).
  const otherCertifications = values.competencies?.other_certifications ?? [];
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
  const saveLabel =
    saveLabelOverride ?? (isUpdate ? '확인하고 이력서 최신화' : '확인하고 이력서 저장');
  const canSave = values.can_save === true && !confirm.isPending;
  const queue = questionQueue(values.next_question, values.question_queue);
  const careerYears = prefs?.experience_summary;

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
            <Button
              onClick={() => confirm.mutate(undefined, { onSuccess: onSaved })}
              disabled={!canSave}
            >
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

      <ResumeSection title="기본정보" hint="고용24 회원정보에서 연동돼요. 여기서는 고칠 수 없어요">
        {profile ? (
          <>
            <FieldRow label="성명" value={profile.name} chip={WORK24_CHIP} />
            <FieldRow
              label="생년·성별"
              value={[profile.birth_year && `${profile.birth_year}년생`, profile.gender]
                .filter(Boolean)
                .join(' · ')}
              chip={WORK24_CHIP}
            />
            <FieldRow label="휴대전화" value={profile.phone ?? null} chip={WORK24_CHIP} />
            <FieldRow label="이메일" value={profile.email ?? null} chip={WORK24_CHIP} />
            <FieldRow label="주소" value={profile.address ?? null} chip={WORK24_CHIP} />
          </>
        ) : (
          <FieldRow label="성명·연락처·주소" value="고용24 회원정보에서 자동" chip={WORK24_CHIP} />
        )}
      </ResumeSection>

      <ResumeSection title="학력사항" isRequired isDone={done.education}>
        {education.length === 0 && (
          // 학력이 비어 있어도 학력부터 고를 수 있게 첫 학력 줄을 만듭니다 (시연 검증 5번). 나머지 칸은 고른 뒤 보입니다.
          <FieldRow
            label="학력"
            isRequired
            onEdit={edit('학력')}
            onDirectSave={direct('education', firstEducation)}
            inputKind="select"
            options={EDUCATION_LEVELS}
          />
        )}
        {education.map((item) => {
          const base = `education.${item.item_id}`;
          return (
            <div key={item.item_id} className="py-1">
              <FieldRow
                label="학력"
                value={item.level && (item.is_final ? `${item.level} · 최종학력` : item.level)}
                rawValue={item.level}
                meta={fields[`${base}.level`]}
                isRequired
                onEdit={edit('학력')}
                onDirectSave={direct(`${base}.level`)}
                inputKind="select"
                options={EDUCATION_LEVELS}
              />
              <FieldRow
                label="졸업상태"
                value={item.graduation_status}
                rawValue={item.graduation_status}
                meta={fields[`${base}.graduation_status`]}
                isRequired
                onDirectSave={direct(`${base}.graduation_status`)}
                inputKind="select"
                options={GRADUATION_STATUSES}
              />
              <FieldRow
                label="학교명"
                value={item.school_name}
                rawValue={item.school_name}
                meta={fields[`${base}.school_name`]}
                isRequired
                onDirectSave={direct(`${base}.school_name`)}
              />
              <FieldRow
                label="재학기간"
                value={formatPeriod(item.start_date, item.end_date)}
                rawValue={periodRaw(item.start_date, item.end_date)}
                meta={fields[`${base}.end_date`] ?? fields[`${base}.start_date`]}
                onDirectSave={directPeriod(base)}
                placeholder="1975-03 ~ 1978-02"
              />
              {isCollegeLevel(item) && (
                <>
                  <FieldRow
                    label="전공"
                    value={item.major}
                    rawValue={item.major}
                    meta={fields[`${base}.major`]}
                    isRequired
                    onDirectSave={direct(`${base}.major`)}
                  />
                  <FieldRow
                    label="학점/총점"
                    value={gpaText(item)}
                    rawValue={item.gpa}
                    meta={fields[`${base}.gpa`]}
                    isRequired
                    onDirectSave={direct(`${base}.gpa`)}
                    placeholder="3.8/4.5"
                  />
                </>
              )}
            </div>
          );
        })}
      </ResumeSection>

      <ResumeSection title="희망조건" isRequired isDone={done.prefs}>
        {/* 희망직종·희망지역은 공통코드에서 골라야 해서 대화로만 고칩니다 (백엔드 lookup_code). */}
        <FieldRow
          label="희망직종"
          value={listText(
            prefs?.desired_occupations?.map((o) => occupationText(o)).filter((v) => v !== null),
          )}
          meta={fields['job_preferences.desired_occupations']}
          isRequired
          onEdit={edit('희망 직종')}
        />
        <FieldRow
          label="경력여부"
          value={careerYears}
          rawValue={careerYears}
          meta={fields['job_preferences.experience_summary']}
          isRequired
          // 경력 합계는 코드가 계산해 확인받는 값이라(2-1.4) 대화로만 고칩니다.
          onEdit={edit('희망 직종 경력')}
        />
        <FieldRow
          label="희망직무내용"
          value={prefs?.desired_duties}
          rawValue={prefs?.desired_duties}
          meta={fields['job_preferences.desired_duties']}
          chip={prefs?.desired_duties ? undefined : OPTIONAL_CHIP}
          onEdit={edit('희망직무내용')}
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
          rawValue={salary?.amount ? String(salary.amount) : null}
          meta={fields['job_preferences.desired_salary']}
          isRequired
          onEdit={edit('희망 임금')}
          onDirectSave={direct('job_preferences.desired_salary', toMonthlyWage)}
          inputKind="number"
          placeholder="월 만원 (예: 220)"
        />
        <FieldRow
          label="고용형태"
          value={prefs?.employment_contract_type}
          rawValue={prefs?.employment_contract_type}
          meta={fields['job_preferences.employment_contract_type']}
          isRequired
          onEdit={edit('고용형태')}
          onDirectSave={direct('job_preferences.employment_contract_type')}
          inputKind="select"
          options={CONTRACT_TYPES}
        />
        <FieldRow
          label="병역대체"
          value={prefs?.military_alternative}
          rawValue={prefs?.military_alternative}
          meta={fields['job_preferences.military_alternative']}
          isRequired
          onDirectSave={direct('job_preferences.military_alternative')}
          inputKind="select"
          options={MILITARY_OPTIONS}
        />
        <FieldRow
          label="근무형태 세부"
          value={listText(prefs?.work_arrangements)}
          rawValue={listText(prefs?.work_arrangements)}
          meta={fields['job_preferences.work_arrangements']}
          chip={prefs?.work_arrangements?.length ? undefined : OPTIONAL_CHIP}
          onDirectSave={direct('job_preferences.work_arrangements', toList)}
          placeholder="시간제, 재택근무 희망 (쉼표로 구분)"
        />
        <FieldRow
          label="희망근무시간"
          value={prefs?.desired_working_hours}
          rawValue={prefs?.desired_working_hours}
          meta={fields['job_preferences.desired_working_hours']}
          chip={prefs?.desired_working_hours ? undefined : OPTIONAL_CHIP}
          onDirectSave={direct('job_preferences.desired_working_hours')}
          placeholder="09:00~18:00"
        />
        <FieldRow
          label="그 밖의 희망사항"
          value={prefs?.other_preferences}
          rawValue={prefs?.other_preferences}
          meta={fields['job_preferences.other_preferences']}
          chip={prefs?.other_preferences ? undefined : OPTIONAL_CHIP}
          onDirectSave={direct('job_preferences.other_preferences')}
        />
        <FieldRow
          label="검색키워드"
          value={listText(prefs?.search_keywords)}
          rawValue={listText(prefs?.search_keywords)}
          meta={fields['job_preferences.search_keywords']}
          chip={prefs?.search_keywords?.length ? undefined : OPTIONAL_CHIP}
          onDirectSave={direct('job_preferences.search_keywords', toList)}
          placeholder="시설관리, 전기 (쉼표로 구분, 1~10개)"
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
                rawValue={periodRaw(career.start_date, career.end_date)}
                meta={fields[`${base}.end_date`] ?? fields[`${base}.start_date`]}
                isRequired
                onEdit={edit(`${name} 재직기간`)}
                onDirectSave={directPeriod(base)}
                placeholder="2004-03 ~ 2026-09"
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
                rawValue={career.employment_status}
                meta={fields[`${base}.employment_status`]}
                isRequired
                onDirectSave={direct(`${base}.employment_status`)}
                inputKind="select"
                options={EMPLOYMENT_STATUSES}
              />
              <FieldRow
                label="주요 직무"
                value={career.main_duties}
                rawValue={career.main_duties}
                meta={fields[`${base}.main_duties`]}
                onEdit={edit(`${name} 주요 직무`)}
                onDirectSave={direct(`${base}.main_duties`)}
              />
              <FieldRow
                label="직종"
                value={occupationText(career.occupation)}
                meta={fields[`${base}.occupation`]}
              />
              <FieldRow
                label="급여(월)"
                value={career.monthly_salary ? `${career.monthly_salary}만원` : null}
                rawValue={career.monthly_salary ? String(career.monthly_salary) : null}
                meta={fields[`${base}.monthly_salary`]}
                chip={career.monthly_salary ? undefined : OPTIONAL_CHIP}
                onDirectSave={direct(`${base}.monthly_salary`, Number)}
                inputKind="number"
                placeholder="만원 (예: 250)"
              />
              <FieldRow
                label="기타 사항"
                value={career.additional_details}
                rawValue={career.additional_details}
                meta={fields[`${base}.additional_details`]}
                chip={career.additional_details ? undefined : OPTIONAL_CHIP}
                onDirectSave={direct(`${base}.additional_details`)}
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
            <div key={cert.item_id} className="py-1">
              <FieldRow
                label="자격면허"
                value={cert.certificate_name}
                rawValue={cert.certificate_name}
                meta={fields[`${base}.certificate_name`]}
                isRequired
                onEdit={edit(`${cert.certificate_name ?? '자격증'}`)}
                onDirectSave={direct(`${base}.certificate_name`)}
              />
              <FieldRow
                label="발급기관"
                value={cert.issuing_organization}
                rawValue={cert.issuing_organization}
                meta={fields[`${base}.issuing_organization`]}
                onDirectSave={direct(`${base}.issuing_organization`)}
              />
              <FieldRow
                label="취득일"
                value={formatYm(cert.acquired_date)}
                rawValue={cert.acquired_date}
                meta={fields[`${base}.acquired_date`]}
                onDirectSave={direct(`${base}.acquired_date`)}
                placeholder="2011-05-20"
              />
            </div>
          );
        })}
        <FieldRow
          label="기타자격"
          value={listText(otherCertifications)}
          rawValue={listText(otherCertifications)}
          meta={fields['competencies.other_certifications']}
          chip={otherCertifications.length ? undefined : OPTIONAL_CHIP}
          onDirectSave={direct('competencies.other_certifications', toList)}
          placeholder="쉼표로 구분"
        />
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

      {/* 운전·차량은 완성도에 넣지 않는 선택 칸입니다 (2-1.2, 시연 검증 7번). */}
      <ResumeSection title="운전 및 차량소유">
        <FieldRow
          label="운전가능"
          value={yesNoText(values.additional_info?.can_drive)}
          rawValue={yesNoText(values.additional_info?.can_drive)}
          meta={fields['additional_info.can_drive']}
          chip={values.additional_info?.can_drive == null ? OPTIONAL_CHIP : undefined}
          onDirectSave={direct('additional_info.can_drive', toYesNo)}
          inputKind="select"
          options={YES_NO}
        />
        <FieldRow
          label="차량소지"
          value={yesNoText(values.additional_info?.owns_vehicle)}
          rawValue={yesNoText(values.additional_info?.owns_vehicle)}
          meta={fields['additional_info.owns_vehicle']}
          chip={values.additional_info?.owns_vehicle == null ? OPTIONAL_CHIP : undefined}
          onDirectSave={direct('additional_info.owns_vehicle', toYesNo)}
          inputKind="select"
          options={YES_NO}
        />
      </ResumeSection>

      {queue.length > 0 && !isReadOnly && (
        <section
          className="bg-brand-soft text-brand rounded-xl px-4 py-3"
          aria-label="AI가 물어볼 순서"
        >
          <p className="text-sm font-semibold">AI가 이어서 물어볼 순서</p>
          <ol className="mt-1 flex flex-col gap-0.5 text-sm">
            {queue.map((label, index) => (
              <li key={label} className={index === 0 ? 'font-bold' : undefined}>
                {index + 1}. {label}
                {index === 0 && ' (지금)'}
              </li>
            ))}
          </ol>
        </section>
      )}
    </div>
  );
};

import type { ReactNode } from 'react';

import { ClipboardCheck, FilePen, FileText, type LucideIcon, Route } from 'lucide-react';

import { ICON_SIZE, ICON_STROKE } from '@/lib/iconSize';

/**
 * 로그인 화면 맨 위 서비스 소개: 로고와 무엇을 위해 만들었는지(제목·두 줄)를 한 행에 두고, 아래에 도와주는 일 4가지(한 줄씩).
 * 처음 온 사람이 계정을 고르기 전에 한눈에 알 수 있게 짧게 둡니다.
 */
const CAPABILITIES: { icon: LucideIcon; title: string; description: string }[] = [
  {
    icon: FileText,
    title: '이력서 작성',
    description: '대화와 서류 사진으로 고용24 이력서를 양식 그대로 채워요.',
  },
  {
    icon: Route,
    title: '절차 안내',
    description: '구직등록부터 실업인정까지 지금 할 일과 기한을 알려 드려요.',
  },
  {
    icon: ClipboardCheck,
    title: '구직활동 점검',
    description: '이번 회차에 필요한 활동 건수를 채웠는지 보고, 부족하면 추천해요.',
  },
  {
    icon: FilePen,
    title: '신청서 검토',
    description: '실업인정 신청서를 정리해 드리고, 제출은 본인이 직접 해요.',
  },
];

interface ServiceIntroProps {
  /** 소개 문구 왼쪽에 한 행으로 둘 로고 */
  logo: ReactNode;
}

export const ServiceIntro = ({ logo }: ServiceIntroProps) => (
  <section aria-labelledby="service-heading" className="flex flex-col gap-5">
    <div className="flex flex-wrap items-center gap-x-6 gap-y-3">
      <div className="shrink-0">{logo}</div>
      <div className="flex min-w-0 flex-1 flex-col gap-2">
        <h1 id="service-heading" className="text-3xl font-bold">
          복잡한 실업급여 신청 과정을 도와드려요
        </h1>
        <p className="text-muted text-lg">
          {/* 두 문장을 한 줄씩 보여 줍니다. */}
          <span className="block">
            어려운 이력서 작성부터 구직등록, 실업급여 신청까지 한 번에 간단하게 끝내요.
          </span>
          <span className="block">
            수급 조건에 따라 달라지는 절차를 안내하고, 서류를 잘못 내지 않도록 함께 확인해요.
          </span>
        </p>
      </div>
    </div>
    <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4" aria-label="도와 드리는 일">
      {CAPABILITIES.map(({ icon: Icon, title, description }) => (
        <li key={title} className="bg-panel flex flex-col gap-2 rounded-2xl p-4">
          <span
            aria-hidden
            className="bg-surface text-brand flex size-10 items-center justify-center rounded-xl"
          >
            <Icon size={ICON_SIZE.lg} strokeWidth={ICON_STROKE} />
          </span>
          <h2 className="text-lg font-bold">{title}</h2>
          <p className="text-muted text-base">{description}</p>
        </li>
      ))}
    </ul>
  </section>
);

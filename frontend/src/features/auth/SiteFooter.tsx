/**
 * 계정 화면 맨 아래 바닥글: 링크(소개·GitHub·문의) → 시연 고지(①) → 저작권 표기.
 * 화면 폭 전체에 옅은 회색 바탕을 깔고, 안쪽 내용은 본문과 같은 폭에 맞춥니다.
 */
const REPO_URL = 'https://github.com/dole-guide-ai/dole-guide-ai';

const LINKS = [
  { label: '서비스 소개', href: '#service-heading', isExternal: false },
  { label: 'GitHub', href: REPO_URL, isExternal: true },
  { label: '문의·제안', href: `${REPO_URL}/issues`, isExternal: true },
] as const;

/** 저작권 표기 연도 (빌드 시점 기준) */
const COPYRIGHT_YEAR = new Date().getFullYear();

export const SiteFooter = () => (
  <footer className="bg-panel border-line border-t">
    <div className="text-muted mx-auto flex w-full max-w-6xl flex-col gap-3 px-4 py-8 text-sm">
      <nav aria-label="바닥글 링크">
        <ul className="flex flex-wrap items-center gap-x-3 gap-y-1">
          {LINKS.map(({ label, href, isExternal }, index) => (
            <li key={label} className="flex items-center gap-3">
              {index > 0 && (
                <span aria-hidden className="text-line">
                  ·
                </span>
              )}
              <a
                href={href}
                {...(isExternal ? { target: '_blank', rel: 'noopener noreferrer' } : {})}
                className="text-ink focus-visible:ring-brand rounded-sm font-semibold hover:underline focus-visible:ring-3 focus-visible:outline-hidden"
              >
                {label}
                {isExternal && <span className="sr-only"> (새 창)</span>}
              </a>
            </li>
          ))}
        </ul>
      </nav>
      <div className="flex flex-col gap-1">
        <p>
          시연용 서비스예요. 대화는 실제 AI 에이전트가 답하지만, 고용24와는 연결되어 있지 않아
          실제로 신청되지는 않아요.
        </p>
        <p>계정은 모두 가상 인물이고, 실제 개인정보는 쓰지 않아요.</p>
      </div>
      <p>© {COPYRIGHT_YEAR} 실업급여 길잡이 · dole-guide-ai. All rights reserved.</p>
    </div>
  </footer>
);

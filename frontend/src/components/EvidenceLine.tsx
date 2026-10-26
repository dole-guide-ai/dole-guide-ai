import type { CiteLink } from '@/types/chat.types';

/** 근거 줄 (2-0.8). 규칙·절차를 말한 말풍선과 패널 상자 아래에만 붙입니다.
 * 원문 링크(`links`)가 있으면 출처 이름을 눌러 새 창에서 엽니다. */
interface EvidenceLineProps {
  cite: string;
  links?: CiteLink[];
}

const LINK_SEPARATOR = ' / ';

export const EvidenceLine = ({ cite, links }: EvidenceLineProps) => {
  const linked = links?.filter((link) => link.url) ?? [];
  return (
    <p className="text-muted text-sm">
      <span className="font-medium">근거</span> ·{' '}
      {linked.length === 0
        ? cite
        : linked.map((link, index) => (
            <span key={`${link.url}-${index}`}>
              {index > 0 && LINK_SEPARATOR}
              <a
                href={link.url ?? undefined}
                target="_blank"
                rel="noopener noreferrer"
                className="underline underline-offset-2"
              >
                {link.title}
              </a>
              {link.updated_on && ` · ${link.updated_on}`}
            </span>
          ))}
    </p>
  );
};

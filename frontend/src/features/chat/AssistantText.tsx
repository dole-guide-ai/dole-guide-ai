import ReactMarkdown from 'react-markdown';

import remarkBreaks from 'remark-breaks';

import { ALLOWED_ELEMENTS, trimOpenEmphasis } from '@/features/chat/assistantMarkdown';

interface AssistantTextProps {
  text: string;
}

// 허용하지 않은 요소(링크·이미지 등)는 태그만 벗기고 글자는 남깁니다. HTML은 그리지 않습니다(skipHtml).
export const AssistantText = ({ text }: AssistantTextProps) => (
  <div className="text-ink flex flex-col gap-2 text-base leading-relaxed [&_ol]:list-decimal [&_ol]:pl-6 [&_strong]:font-bold [&_ul]:list-disc [&_ul]:pl-6">
    <ReactMarkdown
      remarkPlugins={[remarkBreaks]}
      allowedElements={ALLOWED_ELEMENTS}
      unwrapDisallowed
      skipHtml
    >
      {trimOpenEmphasis(text)}
    </ReactMarkdown>
  </div>
);

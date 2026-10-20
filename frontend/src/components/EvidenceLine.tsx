/** 근거 줄 (2-0.8). 규칙·절차를 말한 말풍선과 패널 상자 아래에만 붙입니다. */
interface EvidenceLineProps {
  cite: string;
}

export const EvidenceLine = ({ cite }: EvidenceLineProps) => (
  <p className="text-muted text-sm">
    <span className="font-medium">근거</span> · {cite}
  </p>
);

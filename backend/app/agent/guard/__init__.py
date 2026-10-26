"""보안 가드레일 (노션 「AI 설계」 5절).

여러 층 중 모델 앞뒤에서 글을 판정하는 층입니다. 최종 경계는 도구의 결정적 검사
(`ToolContext.allowed_paths`, 신청서 선택지, 서비스 검증)이고, 여기 판정은 그 위에 얹는 신호입니다.

- 입력 판정(`check_input`): 사용자 글 · 서류에서 읽은 글 · 검색 자료에 든 지시 주입을 막습니다.
- 출력 판정(`check_output`): 수급 · 인정 단정, 개인정보를 거릅니다.

판정 백엔드는 설정 `guard_backends`로 고릅니다(backends.py). 규칙 패턴(`rules`)은 늘 켜져 있습니다.
트레이스 · 로그에는 판정 결과(라벨)만 남기고 글은 남기지 않습니다.
"""

from app.agent.guard.backends import Verdict, check_input, check_output, untrusted

__all__ = ["Verdict", "check_input", "check_output", "untrusted"]

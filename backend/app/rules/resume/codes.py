"""이름 칸과 고용24 공통코드 칸의 짝(자격면허명 ↔ 자격면허코드, 전공 ↔ 전공코드). LLM·DB 없음.

이름 칸은 사람이 읽는 글(브리핑·불러오기·화면이 그대로 씀)이고, 코드 칸은 직종과 같은
`{code, name, status, said}`입니다. 이름을 쓰면 코드 칸도 같이 맞추고(대화·불러오기), 코드를 고르면
이름 칸도 공식 이름으로 같이 씁니다(화면 직접 고르기·후보 버튼). 짝은 이 표 하나로 정합니다.
"""

from typing import Any

from app.rules.resume.fields import form_fields
from app.rules.work24_codes import CodeKind, code_done, has_codes, match_code, said_name

# 이름 칸 → (코드 칸, 코드 종류)
NAMED_CODES: dict[str, tuple[str, CodeKind]] = {
    "certificate_name": ("certificate_code", "license"),
    "major": ("major_code", "major"),
}
# 코드 칸 → (이름 칸, 코드 종류)
CODE_NAMES: dict[str, tuple[str, CodeKind]] = {
    code: (name, kind) for name, (code, kind) in NAMED_CODES.items()
}


def code_for_name(name_path: str, text: Any, data: Any = None) -> list[tuple[str, Any]]:
    """이름 칸에 쓴 글 → 같이 쓸 코드 칸 값. 짝이 없거나 코드표가 아직 없으면 빈 목록.

    `data`(지금 이력서)를 주면, 같은 이름으로 이미 코드를 골랐거나 이름만 적기로 한 칸은 그대로
    둡니다(같은 이름을 다시 말해도 고른 값을 지우고 다시 묻지 않게).
    """
    base, _, field = name_path.rpartition("/")
    if field not in NAMED_CODES or not isinstance(text, str) or not text.strip():
        return []
    code_field, kind = NAMED_CODES[field]
    code_path = f"{base}/{code_field}"
    if data is not None:
        current = dict(form_fields(data)).get(code_path)
        value = current.value if current else None
        if code_done(value) and text.strip() in {said_name(value), value.get("name")}:
            return []
    return [(code_path, match_code(kind, text))] if has_codes(kind) else []


def name_path_of(code_path: str) -> str | None:
    """코드 칸 경로 → 짝인 이름 칸 경로(`.../certificate_code` → `.../certificate_name`)."""
    base, _, field = code_path.rpartition("/")
    return f"{base}/{CODE_NAMES[field][0]}" if field in CODE_NAMES else None


def name_for_code(code_path: str, value: Any) -> list[tuple[str, Any]]:
    """코드 칸에 고른 값 → 같이 쓸 이름 칸 값(공식 이름). 짝이 없으면 빈 목록."""
    base, _, field = code_path.rpartition("/")
    if field not in CODE_NAMES or not isinstance(value, dict) or not value.get("name"):
        return []
    return [(f"{base}/{CODE_NAMES[field][0]}", value["name"])]


def code_kind_of(path: str) -> CodeKind | None:
    """`/certifications/q1/certificate_code` 같은 코드 칸 경로의 종류."""
    return CODE_NAMES.get(path.rpartition("/")[2], (None, None))[1]

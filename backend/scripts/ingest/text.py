"""HTML 잡음 제거와 텍스트 정규화."""

import re

from bs4 import BeautifulSoup, Tag

NOISE_TAGS = ("script", "style", "noscript", "iframe", "button")
BLOCK_TAGS = ("p", "div", "li", "tr", "h3", "h4", "h5")
_SPACES = re.compile(r"[ \t\r\f\v ​　]+")
_NEWLINES = re.compile(r"\s*\n\s*")


def soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "lxml")


def strip_noise(node: Tag) -> Tag:
    for tag in node.find_all(NOISE_TAGS):
        tag.decompose()
    return node


def clean(text: str) -> str:
    """공백을 하나로 줄이고 줄바꿈은 한 개만 남깁니다."""
    text = _SPACES.sub(" ", text)
    return _NEWLINES.sub("\n", text).strip()


def text_of(node: Tag | None) -> str:
    """편집기 HTML은 글자를 span 조각으로 나누므로 구분자 없이 이어 붙입니다."""
    if node is None:
        return ""
    for br in node.find_all("br"):
        br.replace_with("\n")
    for block in node.find_all(BLOCK_TAGS):
        block.append("\n")
    return clean(node.get_text(""))

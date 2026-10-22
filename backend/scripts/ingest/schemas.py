"""파싱 결과 JSON 형식. 필수 칸이 빠지면 저장 단계에서 바로 실패합니다."""

from typing import Literal

from pydantic import BaseModel, Field

SectionType = Literal[
    "overview",
    "benefits",
    "eligibility",
    "procedure",
    "cautions",
    "documents",
    "appeals",
    "faq",
    "related",
    "other",
]
BlockType = Literal["paragraph", "heading", "list", "step", "table", "faq", "link"]


class FaqCatalogItem(BaseModel):
    faq_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    summary: str
    list_page: int
    list_position: int
    detail_url: str


class FaqDetail(BaseModel):
    faq_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    published_at: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    question: str = Field(min_length=1)
    answer: str = Field(min_length=1)
    attachments: list[str] = []
    source_url: str
    metadata: dict[str, str] = {"priority": "secondary"}


class PolicyCatalogItem(BaseModel):
    policy_id: str = Field(pattern=r"^SI\d+$")
    syst_cl_id: str
    policy_name: str = Field(min_length=1)
    target_label: str
    category_label: str
    summary: str
    list_page: int
    list_position: int
    detail_url: str

    @property
    def key(self) -> str:
        """같은 정책 ID가 분류(systClId)만 달리해 여러 정책으로 쓰이므로 둘을 묶어 구분합니다."""
        return f"{self.policy_id}_{self.syst_cl_id}"


class Block(BaseModel):
    block_id: str
    type: BlockType
    order: int
    text: str = ""
    items: list[str] = []
    rows: list[list[str]] = []
    question: str = ""
    answer: str = ""
    step_number: int | None = None
    url: str = ""


class PolicySection(BaseModel):
    section_id: str
    original_title: str
    section_type: SectionType
    order: int
    text: str
    blocks: list[Block]


class RelatedLink(BaseModel):
    name: str
    url: str


class PolicyDetail(BaseModel):
    policy_id: str = Field(pattern=r"^SI\d+$")
    syst_cl_id: str = ""
    title: str = Field(min_length=1)
    source_url: str
    last_modified: str | None = None
    toc: list[str] = []  # 화면 오른쪽 목차. 검증에서 sections와 대조합니다.
    sections: list[PolicySection]
    related_links: list[RelatedLink] = []
    related_policies: list[str] = []


ChunkScope = Literal["catalog", "content", "faq"]
ChunkType = Literal["catalog", "section", "step", "faq", "table", "faq_pair"]


class Chunk(BaseModel):
    """임베딩 직전 검색 청크. content가 임베딩·LLM에 들어가는 텍스트입니다."""

    chunk_id: str = Field(min_length=1)
    chunk_scope: ChunkScope
    chunk_type: ChunkType
    policy_id: str | None = None  # 고용24 정책 키(정책ID_분류ID)
    faq_id: str | None = None
    section_id: str | None = None
    section_type: SectionType | None = None
    sequence: int
    content: str = Field(min_length=1)
    # 원문 추적용: 이 청크가 담은 블록 ID. 검증에서 빠진 블록이 없는지 확인합니다.
    block_ids: list[str] = []
    metadata: dict[str, str | bool | int | None] = {}

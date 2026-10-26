"""이력서 인터뷰 시나리오. 가상 사용자가 아는 사실(정답)과 말투를 정합니다. 모두 합성 값입니다.

에이전트가 사용자를 이끌어 이력서 칸을 채우는지 봅니다. 사용자는 물어본 것만 답하므로,
에이전트가 묻지 않은 칸은 채워지지 않습니다.
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class CareerFact:
    company: str
    start: str  # YYYY-MM (정답)
    end: str  # YYYY-MM
    duties: tuple[str, ...]  # 하던 일 핵심어. 하나라도 답에 들어가면 맞음
    position: str | None = None  # 직급·직책. None이면 "없었다"가 정답(칸은 비거나 없음)
    occupation: str | None = None  # 직종 핵심어
    # 처음 말할 때 쓰는 표현(정확하지 않음). 다시 물으면 정답을 말합니다.
    vague: str = ""


@dataclass(frozen=True)
class Scenario:
    id: str
    title: str
    opening: str  # 사용자의 첫 말
    style: str  # 가상 사용자에게 주는 말투·행동 지시
    careers: tuple[CareerFact, ...]
    education: str | None = None  # 최종 학력 핵심어(고등학교·대학교)
    certifications: tuple[str, ...] = ()
    desired_job: str | None = None
    region: str | None = None
    extra: tuple[str, ...] = field(default_factory=tuple)  # 사용자가 아는 그 밖의 사실


SCENARIOS: tuple[Scenario, ...] = (
    Scenario(
        id="I-01",
        title="협조적이고 정확하게 답함",
        opening="이력서 쓰려고요. 어떻게 하면 돼요?",
        style="묻는 것에 정확한 날짜와 이름으로 또박또박 답한다.",
        careers=(
            CareerFact(
                "한빛물류",
                "2012-03",
                "2026-09",
                ("입출고", "재고"),
                "반장",
                "물류",
            ),
        ),
        education="고등학교",
        certifications=("지게차운전기능사",),
        desired_job="물류",
        region="인천",
    ),
    Scenario(
        id="I-02",
        title="날짜를 모호하게 말함",
        opening="회사 다닌 거 적어야 하죠? 대성기계 다녔어요.",
        style="날짜는 처음엔 모호하게 말하고, 몇 년 몇 월인지 콕 집어 다시 물으면 정확히 답한다.",
        careers=(
            CareerFact(
                "대성기계",
                "2024-12",
                "2026-09",
                ("조립", "부품"),
                None,
                "생산",
                vague="재작년 겨울쯤부터 지난달까지",
            ),
        ),
        education="고등학교",
        desired_job="생산",
        region="경기",
    ),
    Scenario(
        id="I-03",
        title="아주 짧게 답함",
        opening="이력서요",
        style="한두 단어로만 짧게 답한다. 하던 일도 처음엔 '포장'처럼 한 단어로 말하고, "
        "구체적으로 물으면 그때 조금 더 말한다.",
        careers=(
            CareerFact(
                "세진식품",
                "2015-05",
                "2026-09",
                ("포장", "검수"),
                None,
                "포장",
            ),
        ),
        education="중학교",
        desired_job="포장",
        region="부천",
    ),
    Scenario(
        id="I-04",
        title="한 번에 여러 사실을 섞어 말함",
        opening="고등학교 나와서 2004년 3월부터 올해 9월까지 OO산업에서 기계 정비했고 "
        "전기기능사 있어요.",
        style="처음에 여러 사실을 한꺼번에 말하고, 그 뒤엔 묻는 것에만 답한다.",
        careers=(
            CareerFact(
                "OO산업",
                "2004-03",
                "2026-09",
                ("정비", "기계"),
                "주임",
                "정비",
            ),
        ),
        education="고등학교",
        certifications=("전기기능사",),
        desired_job="설비",
        region="안산",
    ),
    Scenario(
        id="I-05",
        title="직종과 직급을 섞어 말함",
        opening="동해금속에서 생산직 반장으로 있었어요.",
        style="직종과 직급을 한 말에 섞어 말한다. 기간은 물으면 정확히 답한다.",
        careers=(
            CareerFact(
                "동해금속",
                "2010-01",
                "2026-09",
                ("프레스", "작업"),
                "반장",
                "생산",
            ),
        ),
        education="고등학교",
        desired_job="생산",
        region="울산",
    ),
    Scenario(
        id="I-06",
        title="경력이 둘, 나중에 떠올림",
        opening="최근엔 미래택배에서 배송 일 했어요.",
        style="처음엔 최근 경력만 말한다. 에이전트가 그 전에 다른 곳이 있는지 물으면 "
        "두 번째 경력을 말한다. 묻지 않으면 말하지 않는다.",
        careers=(
            CareerFact(
                "미래택배",
                "2019-04",
                "2026-09",
                ("배송", "택배"),
                None,
                "배송",
            ),
            CareerFact(
                "삼호운수",
                "2008-02",
                "2019-03",
                ("화물", "운전"),
                None,
                "운전",
            ),
        ),
        education="고등학교",
        certifications=("1종 대형",),
        desired_job="배송",
        region="서울",
    ),
    Scenario(
        id="I-07",
        title="입사 월을 기억 못 함",
        opening="이력서 쓸게요. 그린마트에서 일했어요.",
        style="입사는 2005년인 것만 기억하고 월은 끝까지 모른다고 답한다. 대략이라도 말해 "
        "달라고 하면 '봄쯤'이라고 한다. 다른 건 정확히 답한다.",
        careers=(
            CareerFact(
                "그린마트",
                "2005-04",
                "2026-09",
                ("진열", "계산"),
                None,
                "판매",
                vague="2005년쯤부터 지난달까지",
            ),
        ),
        education="고등학교",
        desired_job="판매",
        region="대전",
    ),
    Scenario(
        id="I-08",
        title="중간에 다른 질문을 끼워 넣음",
        opening="이력서 써야 하는데 해성건설에서 현장 관리했어요.",
        style="두 번째 답할 때 '근데 실업급여는 언제부터 나와요?'라고 딴 질문을 끼워 넣고, "
        "그 뒤엔 다시 묻는 것에 답한다.",
        careers=(
            CareerFact(
                "해성건설",
                "2011-06",
                "2026-09",
                ("현장", "관리"),
                "과장",
                "건설",
            ),
        ),
        education="대학교",
        desired_job="건설",
        region="세종",
    ),
)

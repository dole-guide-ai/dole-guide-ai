import pytest
from sqlalchemy.orm import Session

from app.services.work24_codes import load_codes, lookup_code, name_only

pytestmark = pytest.mark.integration

# 실제 응답과 같은 계층의 합성 XML. 직종 0263은 같은 경로가 두 번 와도 한 번만 들어가야 합니다.
REGION_XML = """<?xml version="1.0" encoding="UTF-8"?><cmcdRegion><total>3</total>
<oneDepth><regionCd>41000</regionCd><regionNm>경기</regionNm>
<twoDepth><regionCd>41550</regionCd><regionNm>경기 안성시</regionNm>
<superCd>41000</superCd></twoDepth>
<twoDepth><regionCd>41220</regionCd><regionNm>경기 평택시</regionNm>
<superCd>41000</superCd></twoDepth>
</oneDepth></cmcdRegion>""".encode()

JOBS_XML = """<?xml version="1.0" encoding="UTF-8"?><cmcdJobs><total>5</total>
<oneDepth><jobsCd>02</jobsCd><jobsNm>경영·사무</jobsNm>
<twoDepth><jobsCd>026</jobsCd><jobsNm>경영지원 사무</jobsNm><superCd>02</superCd>
<threeDepth><jobsCd>026301</jobsCd><jobsNm>인사 사무원</jobsNm><superCd>026</superCd></threeDepth>
<threeDepth><jobsCd>026301</jobsCd><jobsNm>인사 사무원</jobsNm><superCd>026</superCd></threeDepth>
<threeDepth><jobsCd>026302</jobsCd><jobsNm>노무 사무원</jobsNm><superCd>026</superCd></threeDepth>
<threeDepth><jobsCd>026600</jobsCd><jobsNm>감사 사무원</jobsNm><superCd>026</superCd></threeDepth>
<threeDepth><jobsCd>026700</jobsCd><jobsNm>총무 사무원</jobsNm><superCd>026</superCd></threeDepth>
</twoDepth></oneDepth></cmcdJobs>""".encode()


@pytest.fixture
def codes(db_session: Session) -> Session:
    assert load_codes(db_session, REGION_XML, JOBS_XML) == (3, 6)
    return db_session


def test_lookup_returns_at_most_three(codes: Session) -> None:
    found = lookup_code(codes, "occupation", "사무원")
    assert len(found) == 3
    assert all(c.code.startswith("026") for c in found)
    assert [c.name for c in lookup_code(codes, "occupation", "인사사무원")] == ["인사 사무원"]


def test_lookup_region_and_no_match(codes: Session) -> None:
    assert [(c.code, c.name) for c in lookup_code(codes, "region", "안성")] == [
        ("41550", "경기 안성시")
    ]
    assert lookup_code(codes, "occupation", "우주비행사") == []
    assert lookup_code(codes, "region", "  ") == []


def test_name_only_after_three_misses() -> None:
    assert name_only(" 프레스 반장 ") == {
        "code": None,
        "name": "프레스 반장",
        "status": "name_only",
    }

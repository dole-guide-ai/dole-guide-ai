"""수급자격 신청 경로: 인터넷 사전제출이 되는지, 센터 방문이 필요한지 (PROC-048). 순수 함수.

이직일 기준 만 65세 이상이면 인터넷 사전제출 대상이 아니라 관할 고용센터에 방문해 신청합니다.
첫 안내·브리핑·계정 응답·안내 목록이 모두 이 한 곳의 기준을 씁니다.
"""

from app.schemas.procedure import Stage

ONLINE_PRESUBMIT_MAX_AGE = 65
PRESUBMIT_RULE = "PROC-048"
# 수급자격 신청 전 단계. 이 단계에서만 신청 경로 안내가 의미가 있습니다.
PRESUBMIT_STAGES = (Stage.JOB_REGISTRATION, Stage.EDUCATION, Stage.ELIGIBILITY_APPLICATION)


def online_presubmit(age_at_separation: int) -> bool:
    """인터넷 사전제출 대상인지(이직일 기준 만 65세 미만)."""
    return age_at_separation < ONLINE_PRESUBMIT_MAX_AGE


def visit_to_apply(age_at_separation: int, stage: str | None) -> bool:
    """지금 단계에서 수급자격 신청을 센터 방문으로 해야 한다고 알려야 하는지."""
    return not online_presubmit(age_at_separation) and stage in PRESUBMIT_STAGES

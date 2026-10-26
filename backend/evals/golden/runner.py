"""골든셋 문항을 실제 서비스 흐름으로 돌립니다 (`adapter.run_agent`가 부름).

문항의 상태값으로 평가용 계정 seed를 만들어 테스트 DB에 넣고,
사용자 말마다 `services/chat.start_turn`으로 한 턴씩 돌린 뒤
화면이 읽는 값(이력서·활동·회차·신청서)을 프론트 타입 경로로 모읍니다.
DB는 테스트 트랜잭션 안에서만 쓰고 끝나면 롤백합니다(`db_session` 픽스처).
"""

import shutil
from datetime import date, datetime, time
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.core.clock import KST
from app.core.config import get_settings
from app.repositories import accounts as account_repo
from app.rules import periods
from app.rules.activity_table import load_rules, required_evidence
from app.rules.entry_text import ONLINE_PRESUBMIT_MAX_AGE
from app.schemas.common import FieldStatus
from app.schemas.files import FilePurpose
from app.schemas.messages import MessageCreate
from app.schemas.procedure import Stage
from app.schemas.resume import ResumeStatus
from app.services import accounts as account_service
from app.services import activities as activity_service
from app.services import application as application_service
from app.services import chat as chat_service
from app.services import files as files_service
from app.services import resume as resume_service
from app.services import rounds as round_service
from app.services.accounts import AccountContext
from app.services.entry import ResumeState
from app.services.visitors import authenticate, create_visitor
from evals.golden.adapter import AgentResult
from evals.golden.schema import FILES_DIR

# 문항 상태값에 없는 값. 결과에 영향이 없도록 시연 계정과 비슷한 값으로 둡니다.
INSURED_YEARS = 10.0
RECOGNITION_INTERVAL_DAYS = 28
# 계정 이름. 시연 계정은 합성 서류(경력증명서 등)에 적힌 이름과 같게 두어, 서류의 이름이
# 본인과 다른지 확인하는 동작을 평가할 수 있게 합니다. 나머지는 서류와 겹치지 않는 이름입니다.
PERSONA_NAMES = {"park": "박진수", "park2": "박진수", "choi": "최영수", "lee": "이정호"}
DEFAULT_NAME = "평가계정"
# 골든셋 상태값 resume_status에서 이력서가 없다는 값(나머지는 ResumeState와 같음)
NO_RESUME = "none"


def run_case(db: Session, case: dict[str, Any]) -> AgentResult:
    case_input = case["input"]
    state = case_input["state"]
    today = date.fromisoformat(state["demo_today"])
    now = datetime.combine(today, time.fromisoformat(state["demo_time"]), KST)
    account = _enter(db, case["id"], case_input, today, now)

    # '변경금지' 칸은 대화 전 DB 값과 비교합니다(문항 입력과 서버 모양이 달라서).
    initial = _snapshot(db, account, today, now)
    replies: list[str] = []
    next_action: str | None = None
    cites: list[str] = []
    # 첨부는 화면처럼 먼저 올리고 첫 말에 붙입니다. 실물은 평가가 끝나면 지웁니다.
    try:
        file_ids = _upload_files(db, account, case_input["files"], state["stage"])
        for text in case_input["messages"]:
            message = MessageCreate(text=text, file_ids=file_ids)
            file_ids = []
            turn = chat_service.start_turn(db, account, message, None, today)
            events = list(turn.events())
            turn.finish()
            # 화면에 보이는 답 = 글자 + 되묻기 질문(ask_user). 질문만 하고 끝난 턴도 답이 있습니다.
            replies.append(
                "".join(e.data.text for e in events if e.name in ("token", "ask_user")).strip()
            )
            cites.extend(e.data.cite for e in events if e.name == "done" and e.data.cite)
            next_action = next(
                (e.data.next_action for e in events if e.name == "done"), next_action
            )
        data = _snapshot(db, account, today, now)
    finally:
        shutil.rmtree(Path(get_settings().upload_dir) / str(account.user_id), ignore_errors=True)

    return AgentResult(
        replies=replies,
        next_action=next_action,
        data=data,
        initial_data=initial,
        cites=cites,
    )


def _upload_files(db: Session, account: AccountContext, names: list[str], stage: str) -> list[str]:
    """문항 첨부를 그 계정에 올립니다. 용도는 화면과 같이 구직등록 단계면 이력서 서류(판독 뒤 삭제),
    그 뒤면 구직활동 증빙입니다(frontend useFileUpload.purposeForStage)."""
    purpose = FilePurpose.RESUME_DOC if stage == Stage.JOB_REGISTRATION else FilePurpose.EVIDENCE
    file_ids = []
    for name in names:
        with (FILES_DIR / name).open("rb") as stream:
            created = files_service.upload(db, account, name, stream, purpose, None)
        file_ids.append(created.file_id)
    return file_ids


def _enter(
    db: Session, case_id: str, case_input: dict[str, Any], today: date, now: datetime
) -> AccountContext:
    persona_id = f"eval_{case_id}"
    seed = _seed(case_input, today)
    account_repo.add_all(
        db, [account_repo.Persona(persona_id=persona_id, display={}, seed=seed, sort_order=999)]
    )
    visitor = create_visitor(db, now)
    ctx = authenticate(db, visitor.visitor_token, now)
    account_service.enter(db, ctx.visitor_id, persona_id, today)
    return account_service.find_account(db, ctx.visitor_id, persona_id)


def _offset(day: str | None, today: date) -> int | None:
    return None if day is None else (date.fromisoformat(day) - today).days


def _seed(case_input: dict[str, Any], today: date) -> dict[str, Any]:
    """문항 상태값(evals/golden/presets.BASE 칸) → personas.json 형식 seed (입장일 = 오늘)."""
    state = case_input["state"]
    applied = state["eligibility_applied_date"]
    done = state["completed_rounds"]
    first = None
    if applied and state["next_recognition_date"]:
        # 다음 인정일에서 끝낸 회차만큼 28일씩 되돌립니다. 휴일 조정은 build_rounds가 합니다.
        nxt = date.fromisoformat(state["next_recognition_date"])
        first = (nxt.toordinal() - RECOGNITION_INTERVAL_DAYS * done) - today.toordinal()
    group = periods.recipient_group(
        state["age_at_separation"], state["has_disability"], state["recipient_type"] == "repeat"
    )
    seed: dict[str, Any] = {
        "profile": {"name": PERSONA_NAMES.get(case_input["persona"], DEFAULT_NAME)},
        "procedure": {
            "stage": state["stage"],
            "recipient_group": group,
            "age_at_separation": state["age_at_separation"],
            "has_disability": state["has_disability"],
            "separation_offset": _offset(state["separation_date"], today),
            "insured_years": INSURED_YEARS,
            "education_done": state["education_done"],
            "eligibility_applied_offset": _offset(applied, today),
            "first_recognition_offset": first,
        },
        "submitted_through_round": done,
        "activities": [
            {
                "date_offset": _offset(a["date"], today),
                "category": "job_search",
                "kind": "job_application",
                "route": a.get("route"),
                "org_name": a.get("org_name"),
                "source": "doc",
            }
            for a in case_input["activities"]
        ],
    }
    if resume := _seed_resume(case_input["data"]["resume"], state["resume_status"]):
        seed["resume"] = resume
    return seed


def _seed_resume(resume: dict[str, Any], status: str) -> dict[str, Any] | None:
    """프론트 모양(competencies.careers) → seed 모양(careers). 이력서가 없으면 None."""
    if status == NO_RESUME:
        return None
    competencies = resume["competencies"]
    data = {
        "education": _with_ids(resume["education"], "edu"),
        # 빈 목록은 뺍니다. seed는 빈 목록을 칸 하나로 감싸지 못합니다(desired_regions).
        "job_preferences": {k: v for k, v in resume["job_preferences"].items() if v},
        "careers": _with_ids(competencies["careers"], "career"),
        "certifications": _with_ids(competencies["certifications"], "cert"),
    }
    # draft = 쓰다 만 이력서(저장일 없음).
    # outdated = 퇴사 전에 저장한 이력서라 저장일을 아주 예전으로 둡니다.
    if status == ResumeState.DRAFT:
        return {
            "status": ResumeStatus.DRAFT.value,
            "field_status": FieldStatus.CONFIRMED.value,
            "data": data,
        }
    saved_offset = -3650 if status == ResumeState.OUTDATED else -1
    return {
        "status": ResumeStatus.SAVED.value,
        "saved_offset": saved_offset,
        "field_status": FieldStatus.CONFIRMED.value,
        "data": data,
    }


def _with_ids(items: list[dict[str, Any]], prefix: str) -> list[dict[str, Any]]:
    return [{"item_id": f"{prefix}_{i:03d}", **item} for i, item in enumerate(items, 1)]


def _snapshot(db: Session, account: AccountContext, today: date, now: datetime) -> dict[str, Any]:
    """채점용 결과 데이터. 경로는 프론트 타입과 같습니다(adapter.AgentResult.data)."""
    resume = resume_service.read_resume(db, account).data.model_dump(mode="json")
    values = _values(resume)
    values["competencies"] = {
        **values.get("competencies", {}),
        "careers": values.pop("careers", []),
        "certifications": values.pop("certifications", []),
    }
    # 골든셋 이름(프론트 ResumeValues)에 맞춥니다: 학력 level, 직종 name, 지역 이름 목록.
    for edu in values.get("education", []):
        edu["level"] = edu.get("education_level")
    prefs = values.get("job_preferences", {})
    prefs["desired_occupations"] = [
        {**o, "name": (o.get("occupation") or {}).get("name")}
        for o in prefs.get("desired_occupations", [])
    ]
    prefs["desired_regions"] = [r.get("name") for r in prefs.get("desired_regions") or []]
    activities = activity_service.list_activities(db, account, None, today)
    procedure = account_service.read_procedure(db, account.user_id, today)
    data: dict[str, Any] = {
        "resume": values,
        # 절차 상태: 대화로 교육 이수 등을 알렸을 때 단계가 넘어가는지 봅니다.
        "procedure": {"stage": str(procedure.stage), "education_done": procedure.education_done},
        "activities": [_activity(a.model_dump(mode="json")) for a in activities.items],
        "derived": {
            "rule_group": procedure.recipient_group,
            # 이직 당시 만 65세 미만만 인터넷 사전제출 (entry_text, PROC-048)
            "can_presubmit_online": procedure.age_at_separation < ONLINE_PRESUBMIT_MAX_AGE,
        },
    }
    try:
        check = round_service.read_current(db, account.user_id, today)
    except Exception:  # noqa: BLE001 - 회차가 없는 단계(이력서·교육)는 회차 값이 없습니다
        return data
    # 골든셋의 shortfall(모자란 건수) = 회차 점검의 remaining
    data["round"] = {**check.model_dump(mode="json"), "shortfall": check.remaining}
    application = application_service.read_application(db, account, "current", now)
    data["recognition"] = _values(application.data.model_dump(mode="json"))
    data["derived"].update(
        rule_group=check.rule_group,
        current_round=check.round,
        is_attendance_round=application.attendance_required,
        required=check.required,
        required_job_search=check.required_job_search,
        # 화면의 D-day·대상기간 (DerivedState). 인정일 당일이면 0
        d_day=(check.recognition_date - today).days,
        period={"start": check.period_start.isoformat(), "end": check.period_end.isoformat()},
    )
    return data


def _activity(row: dict[str, Any]) -> dict[str, Any]:
    """서버 활동 → 골든셋 경로 모양(프론트 RoundActivity: date·종류 이름·필요 증빙)."""
    kind = load_rules().kind(row["kind"])
    return {
        **row,
        "date": row["activity_date"],
        "category": kind.label if kind else row["kind"],
        "evidence": {"required": list(required_evidence(row.get("route")) or [])},
    }


def _values(node: Any) -> Any:
    """{value, status, ...} 칸을 값만 남깁니다. 채점 경로는 값 기준입니다."""
    if isinstance(node, dict):
        if "value" in node and "status" in node:
            return node["value"]
        return {key: _values(value) for key, value in node.items()}
    if isinstance(node, list):
        return [_values(item) for item in node]
    return node

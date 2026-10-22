"""실업인정 신청서에서 사용자가 직접 답하는 칸의 구조입니다.

근로·소득, 취업·개인 사업, 산재, 실업크레딧, 통지 방법, 다음 활동 계획, 개인정보 동의가 있고
모든 칸은 사용자 답변으로만 채우며 직접 수정 API로는 고칠 수 없습니다.
구직활동 칸은 여기 없고 activities에서 만듭니다. 칸 이름은 초안이라 리뷰 뒤 바뀔 수 있습니다.
"""

from pydantic import BaseModel

from app.schemas.common import FormField

SCHEMA_VERSION = "work24_recognition_v1"


class WorkAnswers(BaseModel):
    has_work: FormField = FormField()  # yes / no
    # [{item_id, worked_on, hours, income_received_on, amount}]
    entries: FormField = FormField()


class EmploymentAnswers(BaseModel):
    status: FormField = FormField()  # none / employed / self_employed
    started_on: FormField = FormField()


class IndustrialAccidentAnswers(BaseModel):
    receiving: FormField = FormField()  # yes / no


class CreditAnswers(BaseModel):
    application: FormField = FormField()  # wish / not_wish / not_applicable
    notice_method: FormField = FormField()  # electronic / mail
    auto_payment: FormField = FormField()  # wish / not_wish
    income_asset_consent: FormField = FormField()  # agree / disagree


class RecognitionData(BaseModel):
    work: WorkAnswers = WorkAnswers()
    employment: EmploymentAnswers = EmploymentAnswers()
    industrial_accident: IndustrialAccidentAnswers = IndustrialAccidentAnswers()
    credit: CreditAnswers = CreditAnswers()
    notification_method: FormField = FormField()  # sms / email / mail
    next_plan: FormField = FormField()  # [{item_id, kind, planned_on}]
    privacy_consent: FormField = FormField()  # agree_all / agree_required_only / disagree

"""DB 모델을 한 곳에서 불러오는 모듈입니다.

새 모델은 여기서 import해야 alembic autogenerate가 테이블을 인식합니다.
"""

from app.models.activity import Activity
from app.models.file import File, activity_files
from app.models.idempotency_key import IdempotencyKey
from app.models.message import Message
from app.models.persona import Persona
from app.models.procedure_state import ProcedureState
from app.models.recognition_application import RecognitionApplication
from app.models.resume import Resume
from app.models.round import Round
from app.models.user import User
from app.models.user_profile import UserProfile
from app.models.visitor import Visitor
from app.models.work24_code import CmcdJobs, CmcdRegion

__all__ = [
    "Activity",
    "CmcdJobs",
    "CmcdRegion",
    "File",
    "IdempotencyKey",
    "Message",
    "Persona",
    "ProcedureState",
    "RecognitionApplication",
    "Resume",
    "Round",
    "User",
    "UserProfile",
    "Visitor",
    "activity_files",
]

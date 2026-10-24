"""기본정보 표시값을 만드는 서비스."""

import uuid

from sqlalchemy.orm import Session

from app.repositories import accounts as repo
from app.schemas.profile import ProfileDisplay


def read_profile_display(db: Session, user_id: uuid.UUID) -> ProfileDisplay | None:
    profile = repo.get_profile(db, user_id)
    if profile is None:
        return None
    return ProfileDisplay(
        name=profile.name,
        birth_year=profile.birth_year,
        gender=profile.gender,
        phone=profile.phone,
        email=profile.email,
        address=profile.address,
        bank_name=profile.bank_name,
        account_last4=profile.account_last4,
    )

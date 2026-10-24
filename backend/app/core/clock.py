"""
한국 시간(Asia/Seoul) 기준입니다.
today를 인자로 받으며, 라우터는 Today 의존성으로 날짜를 주입받습니다.
"""

from datetime import date, datetime
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import Depends

KST = ZoneInfo("Asia/Seoul")


def now_kst() -> datetime:
    return datetime.now(KST)


def today_kst() -> date:
    return now_kst().date()


def get_today() -> date:
    return today_kst()


def get_now() -> datetime:
    return now_kst()


Today = Annotated[date, Depends(get_today)]
Now = Annotated[datetime, Depends(get_now)]

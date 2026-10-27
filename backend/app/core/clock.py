"""
한국 시간(Asia/Seoul) 기준입니다.
today를 인자로 받으며, 라우터는 Today·Now 의존성으로 날짜·시각을 주입받습니다.
Today는 Now의 날짜라서, 테스트는 get_now 하나만 고정하면 날짜와 시각이 함께 맞습니다.
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


def get_now() -> datetime:
    return now_kst()


Now = Annotated[datetime, Depends(get_now)]


def get_today(now: Now) -> date:
    return now.date()


Today = Annotated[date, Depends(get_today)]

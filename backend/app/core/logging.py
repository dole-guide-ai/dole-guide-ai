import logging


def setup_logging(level: int = logging.INFO) -> None:
    # 로그에 이름·연락처·발화 원문 등 개인정보를 남기지 않습니다.
    logging.basicConfig(level=level, format="%(asctime)s %(levelname)s %(name)s %(message)s")

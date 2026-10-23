FROM python:3.14-slim
COPY --from=ghcr.io/astral-sh/uv:0.12.24 /uv /bin/uv
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_NO_DEV=1 PYTHONUTF8=1
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY . .
RUN uv sync --frozen --no-dev

# 컨테이너가 탈취돼도 피해를 줄이도록 root가 아닌 사용자로 실행합니다.
# 코드와 .venv는 root 소유로 두어 실행 사용자가 읽기만 할 수 있게 합니다.
RUN useradd --create-home --uid 10001 app
# 업로드 파일(구직활동 증빙)만 실행 사용자가 쓸 수 있게 둡니다. 운영은 볼륨으로 마운트합니다.
RUN mkdir -p /data/uploads && chown app:app /data/uploads
USER app

ENV PATH="/app/.venv/bin:$PATH"
ENV TZ=Asia/Seoul
# 실제 접속자 IP(X-Forwarded-For)를 믿을 프록시 주소. 기본은 자기 자신만, 운영은 compose에서 내부 네트워크로 지정합니다.
ENV FORWARDED_ALLOW_IPS=127.0.0.1
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]

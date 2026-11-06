FROM python:3.13-alpine@sha256:d76f585fb0d5107dd47143da5e61554fd9cae656a30f3470f815cb8475769b6a

# Alpine uses musl instead of the vulnerable glibc in the previous Debian base.
RUN apk upgrade --no-cache \
    && python -m pip uninstall --yes pip

COPY --from=ghcr.io/astral-sh/uv:0.13.6@sha256:af22a52f5eafef3d78e551599d405c02df61919d18028f0cea8eda93bc9986d0 /uv /bin/uv

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH"

COPY pyproject.toml uv.lock README.md ./
COPY src ./src
COPY scripts/run_session_simulations.py ./scripts/run_session_simulations.py
COPY scripts/smoke_table_api.py ./scripts/smoke_table_api.py
COPY scripts/smoke_application.py ./scripts/smoke_application.py
RUN uv sync --locked --no-dev --no-editable --no-cache \
    && addgroup -g 1000 app && adduser -D -u 1000 -G app app

USER app
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2)"]
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-proxy-headers"]

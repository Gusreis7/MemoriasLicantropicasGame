FROM python:3.13-slim@sha256:ae14d4ce8771606477a81446e7ef429edd6762305fc50c84507c1041fa8285d1

# Apply Debian security fixes without changing the Python dependency lock.
# Disable APT retries while upgrading the vulnerable APT bundled in the base.
RUN DEBIAN_FRONTEND=noninteractive apt-get -o Acquire::Retries=0 update \
    && DEBIAN_FRONTEND=noninteractive apt-get -o Acquire::Retries=0 upgrade -y \
    && rm -rf /var/lib/apt/lists/*

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
RUN uv sync --locked --no-dev --no-editable \
    && useradd --create-home app

USER app
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2)"]
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-proxy-headers"]

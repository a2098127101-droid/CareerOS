FROM node:26.7.0-bookworm-slim@sha256:cd565714d4da3e84bfd341e31448f81d47c6362198f152345297c9c1154e6341 AS spatial-build
WORKDIR /workspace
COPY frontend/package.json frontend/package-lock.json ./frontend/
RUN cd frontend \
    && npm ci --ignore-scripts --no-audit --no-fund
COPY frontend ./frontend
RUN cd frontend \
    && npm run build \
    && test -f /workspace/app/static/app/index.html

FROM python:3.11-slim@sha256:db3ff2e1800a8581e2c48a27c3995339d47bdf046da21c7627accd3d51053a93
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
RUN sed -i 's|http://deb.debian.org|https://deb.debian.org|g' /etc/apt/sources.list.d/debian.sources \
    && apt-get -o Acquire::Retries=10 update \
    && apt-get -o Acquire::Retries=10 --fix-missing install -y --no-install-recommends postgresql-client curl \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt requirements.lock ./
RUN pip install --no-cache-dir --require-hashes --retries 10 --timeout 60 \
    --index-url https://pypi.org/simple \
    -r requirements.lock \
    && pip check \
    && pip uninstall --yes setuptools wheel
RUN groupadd --gid 10001 careeros \
    && useradd --uid 10001 --gid careeros --home-dir /app --no-create-home \
       --shell /usr/sbin/nologin careeros
COPY --chown=careeros:careeros . .
COPY --from=spatial-build --chown=careeros:careeros /workspace/app/static/app ./app/static/app
USER 10001:10001
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl --fail --silent http://127.0.0.1:8000/live || exit 1
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

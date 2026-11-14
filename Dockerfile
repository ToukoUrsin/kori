# Kori: FastAPI + DuckDB engine + the built web app, one small container.
FROM node:22-slim AS web
WORKDIR /web
RUN corepack enable
COPY web/package.json web/pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile
COPY web/ ./
RUN pnpm build

FROM python:3.12-slim
# bubblewrap: the jail the chat's sandbox runs in (backend/kori/lab/kernel.py)
RUN apt-get update && apt-get install -y --no-install-recommends bubblewrap && rm -rf /var/lib/apt/lists/*
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
WORKDIR /app/backend
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev
COPY backend/kori ./kori
COPY data/build /app/data/build
COPY data/benchmarks /app/data/benchmarks
COPY --from=web /web/dist /app/web/dist
ENV PYTHONPATH=/app/backend KORI_DATA_DIR=/app/data KORI_WEB_DIST=/app/web/dist PYTHONUNBUFFERED=1
EXPOSE 8080
CMD ["uv", "run", "--no-dev", "uvicorn", "kori.app:app", "--host", "0.0.0.0", "--port", "8080", "--proxy-headers", "--forwarded-allow-ips", "*"]

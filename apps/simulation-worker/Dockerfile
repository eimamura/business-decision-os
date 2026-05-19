FROM python:3.12-slim AS base
WORKDIR /app
RUN pip install uv

FROM base AS builder
COPY pyproject.toml .
COPY packages/ packages/
COPY apps/simulation-worker/ apps/simulation-worker/
RUN uv sync --no-dev

FROM base AS runtime
COPY --from=builder /app /app
ENV PYTHONPATH=/app
CMD ["uv", "run", "python", "apps/simulation-worker/run_job.py"]

FROM python:3.12-slim AS builder
WORKDIR /app
COPY pyproject.toml .
COPY apps/api/ apps/api/
COPY packages/ packages/
COPY config config
RUN pip install uv && uv sync --no-dev

FROM python:3.12-slim
WORKDIR /app
COPY --from=builder /app /app
ENV PYTHONPATH="/app/packages"
CMD ["uv", "run", "uvicorn", "apps.api.main:app", "--host", "0.0.0.0", "--port", "8000"]

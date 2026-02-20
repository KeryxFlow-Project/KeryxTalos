# Stage 1: Build dependencies
FROM python:3.12-slim AS builder

RUN pip install --no-cache-dir poetry==1.8.5

ENV POETRY_VIRTUALENVS_IN_PROJECT=true

WORKDIR /app

# Copy project metadata (README.md is referenced in pyproject.toml)
COPY pyproject.toml README.md ./

# Generate lock file (poetry.lock is gitignored) and install dependencies
RUN poetry lock --no-update && \
    poetry install --without dev --no-root --no-interaction

# Copy source code and install the project itself
COPY keryxflow/ keryxflow/
RUN poetry install --without dev --no-interaction

# Stage 2: Runtime
FROM python:3.12-slim

RUN groupadd --system keryxflow && \
    useradd --system --gid keryxflow --create-home keryxflow

WORKDIR /app

# Copy virtualenv from builder
COPY --from=builder /app/.venv /app/.venv

# Copy application source and config
COPY keryxflow/ keryxflow/
COPY settings.toml .
COPY .env.example .

# Patch settings.toml for demo mode: disable features that require API keys
# (env vars alone won't override TOML values due to pydantic-settings priority)
RUN sed -i 's/^llm_enabled = true/llm_enabled = false/' settings.toml && \
    sed -i 's/^news_enabled = true/news_enabled = false/' settings.toml

# Create data directory for SQLite and logs
RUN mkdir -p data && chown -R keryxflow:keryxflow /app

# Demo mode defaults: paper trading, no LLM (zero API keys needed)
ENV VIRTUAL_ENV=/app/.venv \
    PATH="/app/.venv/bin:$PATH" \
    KERYXFLOW_MODE=paper \
    KERYXFLOW_AGENT_ENABLED=false \
    KERYXFLOW_ORACLE_LLM_ENABLED=false

USER keryxflow

ENTRYPOINT ["keryxflow"]

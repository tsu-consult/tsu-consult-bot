﻿# ---------- Base stage ----------
FROM python:3.12-slim as base

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN pip install --no-cache-dir poetry

COPY pyproject.toml poetry.lock* /app/

# ---------- Build stage ----------
FROM base as builder

RUN poetry config virtualenvs.create false \
 && poetry install --only main --no-interaction --no-ansi

COPY . /app/

# ---------- Runtime stage ----------
FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    build-essential \
 && rm -rf /var/lib/apt/lists/*

COPY --from=builder /app /app
COPY --from=builder /usr/local/lib/python3.12 /usr/local/lib/python3.12
COPY --from=builder /usr/local/bin /usr/local/bin

EXPOSE 8002

CMD ["python", "bot.py"]

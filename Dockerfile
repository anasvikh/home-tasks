# syntax=docker/dockerfile:1.6
FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        tini \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY cleaning_bot ./cleaning_bot

# Ensure runtime directories exist for volumes
RUN mkdir -p /data /backups

ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["python", "-m", "cleaning_bot.bot"]

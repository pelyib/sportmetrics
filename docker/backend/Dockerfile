FROM python:3.11-slim AS builder

WORKDIR /app

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PIP_NO_CACHE_DIR=1
ENV PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

FROM python:3.11-slim AS production

WORKDIR /app

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PATH="/home/appuser/.local/bin:${PATH}"
ENV PYTHONPATH="/home/appuser/.local/lib/python3.11/site-packages:${PYTHONPATH}"

COPY --from=builder /root/.local /home/appuser/.local

# Copy all backend source code
COPY backend/src/ ./src/

# Create necessary directories with proper permissions
RUN mkdir -p /app/output /app/queues /app/state && \
    useradd --create-home --shell /bin/bash appuser && \
    chown -R appuser:appuser /app /home/appuser/.local

USER appuser

# Default to automation mode, but allow override for single processor runs
ENTRYPOINT ["python", "-m", "src.automation.start_automation"]
CMD ["--config", "src/automation/automation_config.json"]

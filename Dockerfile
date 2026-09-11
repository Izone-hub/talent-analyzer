# ============================================================
# Stage 1: Build virtualenv with Python dependencies
# ============================================================
FROM python:3.12-slim AS builder

WORKDIR /build

# Install build tools if native compilation is needed
RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc python3-dev \
    && rm -rf /var/lib/apt/lists/*

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# ============================================================
# Stage 2: Minimal Production Runtime (Internal Only)
# ============================================================
FROM python:3.12-slim AS runner

WORKDIR /app

ENV PATH="/opt/venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Create non-root user and group
RUN groupadd -r -g 10002 analyzeruser \
    && useradd -r -u 10002 -g analyzeruser -d /app analyzeruser

# Copy virtualenv from builder
COPY --from=builder /opt/venv /opt/venv

# Copy application files
COPY --chown=analyzeruser:analyzeruser . /app

# Ensure static and cache directories exist and are writable
RUN mkdir -p /app/static /app/extracted \
    && chown -R analyzeruser:analyzeruser /app

USER analyzeruser

# Internal communication only - do NOT expose to public internet
EXPOSE 8000

HEALTHCHECK --interval=20s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]

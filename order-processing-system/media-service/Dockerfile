# Build stage
FROM python:3.12-slim-bookworm AS builder

# Pin uv version
COPY --from=ghcr.io/astral-sh/uv:0.5.11 /uv /bin/uv

WORKDIR /app

# Install dependencies into a virtualenv
COPY requirements.txt .
RUN uv venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install -r requirements.txt

# Final stage
FROM python:3.12-slim-bookworm

WORKDIR /app

# Upgrade packages and install runtime tools
RUN apt-get update && apt-get upgrade -y && \
    apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy virtualenv
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy source code
COPY src/ ./src/

# Security: Run as non-root user
RUN groupadd -r appgroup && useradd -r -g appgroup -m appuser && \
    chown -R appuser:appgroup /app
USER appuser

EXPOSE 8008

CMD ["uvicorn", "src.app.main:app", "--host", "0.0.0.0", "--port", "8008"]


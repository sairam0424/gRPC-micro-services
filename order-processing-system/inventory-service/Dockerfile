# Build stage
FROM python:3.12-slim-bookworm AS builder

# Pin uv version for reproducibility and security
COPY --from=ghcr.io/astral-sh/uv:0.5.11 /uv /bin/uv

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    python3-dev \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Install dependencies into a virtualenv using uv
RUN uv venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY pyproject.toml .
RUN mkdir -p src/app && touch src/__init__.py src/app/__init__.py

# Install protobuf and project using uv (parallel install)
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install protobuf==4.25.1 && \
    uv pip install .

COPY src/ ./src/
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install .

# Final stage
FROM python:3.12-slim-bookworm

WORKDIR /app

# Upgrade packages in final image to mitigate known vulnerabilities
RUN apt-get update && apt-get upgrade -y && \
    rm -rf /var/lib/apt/lists/*

# Copy the virtualenv from the builder stage
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy source code
COPY src/ ./src/

# Security: Run as non-root user
RUN groupadd -r appgroup && useradd -r -g appgroup -m appuser && \
    chown -R appuser:appgroup /app
USER appuser

# FastAPI port
EXPOSE 8001
# gRPC port
EXPOSE 50052

CMD ["python", "src/app/main.py"]


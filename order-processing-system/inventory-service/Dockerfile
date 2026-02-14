# Build stage
FROM python:3.10-slim-bullseye AS builder

# Install uv for lightning fast builds
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

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
RUN mkdir src
COPY src/ ./src/

# Install protobuf and project using uv (parallel install)
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install protobuf==4.25.1 && \
    uv pip install .

# Final stage
FROM python:3.10-slim-bullseye

WORKDIR /app

# Copy the virtualenv from the builder stage
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy source code
COPY src/ ./src/

# Security: Run as non-root user
RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser

# FastAPI port
EXPOSE 8001
# gRPC port
EXPOSE 50052

CMD ["python", "src/app/main.py"]

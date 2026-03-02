# Build stage
FROM golang:1.24-bookworm AS builder

# Install build tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    build-essential \
    librdkafka-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/* && \
    go install github.com/air-verse/air@v1.61.1

WORKDIR /app

# Download dependencies
COPY order-service/go.mod ./
# Copy saga-orchestrator for the replacement if needed (assuming structure requires it)
COPY saga-orchestrator/ ../saga-orchestrator/

RUN --mount=type=cache,target=/go/pkg/mod \
    go mod download

# Copy source code and build
COPY order-service/ .
RUN --mount=type=cache,target=/go/pkg/mod \
    --mount=type=cache,target=/root/.cache/go-build \
    CGO_ENABLED=1 GOOS=linux go build -ldflags="-s -w" -o main cmd/server/main.go

# Final stage
FROM debian:bookworm-slim

# Upgrade packages and install runtime dependencies
RUN apt-get update && apt-get upgrade -y && \
    apt-get install -y --no-install-recommends \
    librdkafka1 \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Security: Run as non-root user
RUN groupadd -r appgroup && useradd -r -g appgroup -m appuser

# Copy only the compiled binary
COPY --from=builder /app/main .
RUN chown appuser:appgroup main

USER appuser

EXPOSE 50051

CMD ["./main"]


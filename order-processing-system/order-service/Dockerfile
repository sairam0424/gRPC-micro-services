# Build stage
FROM golang:1.24-bookworm AS builder

# Install build tools
RUN apt-get update && apt-get install -y \
    git \
    build-essential \
    librdkafka-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/* && \
    go install github.com/air-verse/air@v1.61.1

WORKDIR /app

# Download dependencies with cache mount
COPY go.mod ./
# COPY go.sum ./
RUN --mount=type=cache,target=/go/pkg/mod \
    go mod download

# Copy source code and build with cache mounts for compiler and modules
COPY . .
RUN --mount=type=cache,target=/go/pkg/mod \
    --mount=type=cache,target=/root/.cache/go-build \
    GOOS=linux go build -ldflags="-s -w" -o main cmd/server/main.go

# Final stage
FROM debian:bookworm-slim
RUN apt-get update && apt-get install -y \
    librdkafka1 \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Security: Run as non-root user
RUN useradd -m appuser
WORKDIR /app

# Copy only the compiled binary
COPY --from=builder /app/main .
RUN chown appuser:appuser main

USER appuser

EXPOSE 50051

CMD ["./main"]

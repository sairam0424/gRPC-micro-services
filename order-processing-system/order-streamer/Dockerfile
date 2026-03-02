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
COPY go.mod go.sum ./
RUN go mod download

# Copy source code and build
COPY . .
RUN --mount=type=cache,target=/go/pkg/mod \
    --mount=type=cache,target=/root/.cache/go-build \
    CGO_ENABLED=1 GOOS=linux go build -ldflags="-s -w" -o order-streamer cmd/server/main.go

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
COPY --from=builder /app/order-streamer .
RUN chown appuser:appgroup order-streamer

USER appuser

EXPOSE 50053

CMD ["./order-streamer"]


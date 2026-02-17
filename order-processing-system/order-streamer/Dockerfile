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

# Download dependencies
COPY go.mod go.sum ./
RUN --mount=type=cache,target=/go/pkg/mod \
    go mod download

# Copy source code and build
COPY . .
RUN --mount=type=cache,target=/go/pkg/mod \
    --mount=type=cache,target=/root/.cache/go-build \
    CGO_ENABLED=1 GOOS=linux go build -ldflags="-s -w" -o order-streamer cmd/server/main.go

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
COPY --from=builder /app/order-streamer .
RUN chown appuser:appuser order-streamer

USER appuser

EXPOSE 50053

CMD ["./order-streamer"]

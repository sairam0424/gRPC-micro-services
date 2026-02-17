# Build stage
FROM golang:1.24-bookworm AS builder

# Install build tools
RUN apt-get update && apt-get install -y \
    git \
    build-essential \
    librdkafka-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Download dependencies
COPY saga-orchestrator/go.mod saga-orchestrator/go.sum ./
RUN --mount=type=cache,target=/go/pkg/mod \
    go mod download

# Copy source code and build
COPY saga-orchestrator/ .
RUN --mount=type=cache,target=/go/pkg/mod \
    --mount=type=cache,target=/root/.cache/go-build \
    CGO_ENABLED=1 GOOS=linux go build -ldflags="-s -w" -o saga-orchestrator cmd/server/main.go

# Final stage
FROM debian:bookworm-slim
RUN apt-get update && apt-get install -y \
    librdkafka1 \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY --from=builder /app/saga-orchestrator .
# We might need doc definitions if they are read at runtime
# (Removed non-existent docs directory copy)

EXPOSE 50054 8081

CMD ["./saga-orchestrator"]

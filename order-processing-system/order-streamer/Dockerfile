# Build stage
FROM golang:1.24-alpine AS builder

# Install build tools
RUN apk add --no-cache git

WORKDIR /app

# Download dependencies with cache mount
COPY go.mod go.sum ./
RUN --mount=type=cache,target=/go/pkg/mod \
    go mod download

# Copy source code and build with cache mounts
COPY . .
RUN --mount=type=cache,target=/go/pkg/mod \
    --mount=type=cache,target=/root/.cache/go-build \
    CGO_ENABLED=0 GOOS=linux go build -ldflags="-s -w" -o order-streamer cmd/server/main.go

# Final stage
FROM alpine:3.19

# Security: Run as non-root user
RUN adduser -D appuser
WORKDIR /app

# Copy only the compiled binary
COPY --from=builder /app/order-streamer .
RUN chown appuser:appuser order-streamer

USER appuser

EXPOSE 50053

CMD ["./order-streamer"]

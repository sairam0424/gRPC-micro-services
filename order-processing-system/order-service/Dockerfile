# Build stage
FROM golang:1.24-alpine AS builder

# Install build tools
RUN apk add --no-cache git && \
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
    CGO_ENABLED=0 GOOS=linux go build -ldflags="-s -w" -o main cmd/server/main.go

# Final stage
FROM alpine:3.19

# Security: Run as non-root user
RUN adduser -D appuser
WORKDIR /app

# Copy only the compiled binary
COPY --from=builder /app/main .
RUN chown appuser:appuser main

USER appuser

EXPOSE 50051

CMD ["./main"]

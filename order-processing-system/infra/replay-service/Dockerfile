FROM golang:1.24-alpine AS builder

WORKDIR /app
COPY go.mod go.sum ./
RUN go mod download
COPY . .
RUN go build -o replay-service .

FROM alpine:latest
WORKDIR /root/
COPY --from=builder /app/replay-service .
ENTRYPOINT ["./replay-service"]

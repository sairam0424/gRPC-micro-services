FROM golang:1.24-alpine AS builder

WORKDIR /app

COPY go.mod go.sum ./
# Unused go.sum check if it exists or just skip if it might not
RUN go mod download

COPY . .
RUN go build -o order-streamer cmd/server/main.go

FROM alpine:latest
WORKDIR /app
COPY --from=builder /app/order-streamer .

EXPOSE 50053
CMD ["./order-streamer"]

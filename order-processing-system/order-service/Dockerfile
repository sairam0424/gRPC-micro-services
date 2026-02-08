FROM golang:1.24-alpine AS builder

WORKDIR /app
COPY go.mod ./
# COPY go.sum ./
RUN go mod download

COPY . .
RUN go build -o main cmd/server/main.go

FROM alpine:latest

WORKDIR /app
COPY --from=builder /app/main .

EXPOSE 50051

CMD ["./main"]

# Order Service (Go-Lang)

The Order Service handles business logic and data management for orders via gRPC.

## Prerequisites
- **Go**: Version 1.20 or higher. [Install Go](https://go.dev/doc/install)
- **Protobuf Compiler (`protoc`)**: For generating gRPC code.
- **Go Plugins for protoc**:
  ```bash
  go install google.golang.org/protobuf/cmd/protoc-gen-go@latest
  go install google.golang.org/grpc/cmd/protoc-gen-go-grpc@latest
  ```

---

## Local Setup

### 1. Initialize and Install Dependencies
If the `go.mod` file is missing or you want to refresh dependencies:
```bash
cd order-service
go mod tidy
```

### 2. Generate gRPC Code
From the project root:
```bash
make generate
```

### 3. Run the Service
```bash
cd order-service
go run cmd/server/main.go
```

---

## Docker Setup

### 1. Build the Image
From the `order-service` directory:
```bash
docker build -t order-service .
```

### 2. Run the Container
```bash
docker run -p 50051:50051 order-service
```

---

## Internal Project Structure
- `cmd/server/`: Main entry point.
- `internal/handler/`: gRPC service implementation (Handlers).
- `internal/service/`: Business logic.
- `pkg/generated/`: Proto-generated Go code.

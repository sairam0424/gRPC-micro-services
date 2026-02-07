# Order Service (Go-Lang)

The Order Service handles business logic and data management for orders via gRPC.

## Prerequisites
- **Go**: Version 1.23 or higher. [Install Go](https://go.dev/doc/install)
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

## API Documentation and REST Gateway

This service implements a dual-mode server:
- **gRPC**: Listening on `:50051`.
- **REST Gateway**: Listening on `:8080` (mapped via `grpc-gateway`).

### Swagger UI
Documentation and interactive Testing:
- **URL**: `http://localhost:8080/swagger/`
- **JSON Spec**: `http://localhost:8080/swagger/order.swagger.json`

### REST Endpoints
- `GET /v1/orders/{order_id}` - Get order by ID.
- `GET /v1/orders` - List all orders.
- `POST /v1/orders` - Create a new order.

Example `curl`:
```bash
curl http://localhost:8080/v1/orders/123
```

---

## Docker Setup

### 1. Build the Image
From the `order-service` directory:
```bash
docker build -t order-service .
```

### 2. Run the Container (Standard Mode)
```bash
docker run -p 50051:50051 order-service
```

### 3. Run in Watch Mode (Hot-Reloading)
From the **project root**, run:
```bash
docker-compose -f docker-compose.dev.yml up order-service
```
*Changes to `.go` files will trigger an automatic rebuild and reload via `air`.*

---

## Advanced Docker Commands

### View Logs
```bash
# Follow logs in real-time
docker logs -f [container_id_or_name]
```

### Interactive Shell
```bash
# Access the container's shell
docker exec -it [container_id_or_name] /bin/sh
```

### Lifecycle Management
```bash
# Stop a container
docker stop [container_id_or_name]

# Remove a container
docker rm [container_id_or_name]
```

---

## Internal Project Structure
- `cmd/server/`: Main entry point.
- `internal/handler/`: gRPC service implementation (Handlers).
- `internal/service/`: Business logic.
- `pkg/generated/`: Proto-generated Go code.

# Order Service (Go-Lang)

The Order Service handles business logic and data management for orders.

## Key Features
- **Standard Layout**: Follows `cmd/`, `internal/`, `pkg/` structure.
- **gRPC Server**: Pure gRPC implementation.
- **Modular**: Business logic is separated into internal services.

## Local Setup

### 1. Initialize Modules
```bash
cd order-service
go mod tidy
```

### 2. Run the Service
```bash
go run cmd/server/main.go
```

## Internal Structure
- `cmd/server/`: Entry point (main.go).
- `internal/handler/`: gRPC handlers implementation.
- `internal/service/`: Business logic.
- `pkg/generated/`: Proto-generated code.

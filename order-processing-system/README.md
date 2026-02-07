# Order Processing System - gRPC Microservices

This project is an industry-standard scaffolding for gRPC microservice communication between a **Python FastAPI Gateway** and a **Go-Lang Order Service**.

## Architecture Overview

The system follows a modern microservices architecture:
- **API Gateway (Python)**: Handles RESTful requests and internal gRPC communication.
- **Order Service (Go)**: Manages business logic for orders.
- **gRPC/Protobuf**: Used for efficient, typesafe internal communication.

For details, see [docs/architecture.md](./docs/architecture.md).

## Quick Start (Docker)

The fastest way to run the entire stack is using Docker Compose.

```bash
# Clone the repository
git clone https://github.com/sairam0424/gRPC-micro-services.git
cd gRPC-micro-services/order-processing-system

# Build and run the services
docker-compose up --build
```

Access the API Gateway at `http://localhost:8000`.

## Local Development Setup

### Prerequisites
- Python 3.10+
- Go 1.20+
- `protoc` compiler

### 1. Generate gRPC Code
Use the Makefile to generate stubs for both Python and Go:
```bash
make generate
```

### 2. Run Services Separately
Refer to individual service READMEs for detailed instructions:
- [API Gateway (Python)](./api-gateway/README.md)
- [Order Service (Go)](./order-service/README.md)

## Makefile Commands
- `make generate`: Generates gRPC stubs from proto files.
- `make clean`: Removes generated files.
- `make up`: Starts services using Docker Compose.
- `make down`: Stops Docker Compose services.

## Project Standards
- **Protobuf Style**: Follows [Google Protobuf Style Guide](./docs/protobuf_style_guide.md).
- **Structure**: Uses standard industry layouts (`src` for Python, `cmd/internal` for Go).

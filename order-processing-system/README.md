# Order Processing System - gRPC Microservices

This project is an industry-standard scaffolding for gRPC microservice communication between a **Python FastAPI Gateway** and a **Go-Lang Order Service**.

## Architecture Overview

The system follows a modern microservices architecture:
- **API Gateway (Python)**: Handles RESTful requests and internal gRPC communication.
- **Order Service (Go)**: Manages business logic and coordinates with Inventory.
- **Inventory Service (Python)**: Manages product stock with PostgreSQL persistence.
- **Web Client (Next.js)**: Modern dashboard for managing orders and stock.
- **Kafka**: Asynchronous message broker for decoupled event processing.
- **Order Streamer (Go)**: Consumes Kafka events and provides gRPC server-streaming.
- **gRPC/Protobuf**: Used for efficient, typesafe internal communication.

For details, see [docs/architecture.md](./docs/architecture.md) and [docs/frontend_integration.md](./docs/frontend_integration.md).

## Quick Start (Docker)

The fastest way to run the entire stack is using Docker Compose.

```bash
# Clone the repository
git clone https://github.com/sairam0424/gRPC-micro-services.git
cd gRPC-micro-services/order-processing-system

# Build and run the services
docker-compose up --build
```

Access the **Web Dashboard** at `http://localhost`.
Access the **API Gateway** via proxy at `http://localhost/api/`.
Access the **Swagger UI** for Go service at `http://localhost/swagger/`.

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

### Build and Run (Standard Mode)
```bash
docker-compose up --build
```

### Build and Run (Development Mode / Watch Mode)
This mode enables hot-reloading for both Python and Go services.
```bash
docker-compose -f docker-compose.dev.yml up --build
```

---

## Neon Setup
1.  **Environment Setup**: Create a `.env` file in the root directory (based on the Neon credentials provided).
2.  **Generate Stubs**: Run `make all` to generate gRPC code.
3.  **Start Services**: Run `docker compose up --build`.

---

## Makefile Commands
- `make generate`: Generates gRPC stubs from proto files.
- `make clean`: Removes generated files.
- `make up`: Starts services using Docker Compose.
- `make up-dev`: Starts services in development mode (hot-reloading).
- `make down`: Stops Docker Compose services.

---

## Project Standards
- **Proto Style**: Follows [Protobuf Style Guide](docs/protobuf_style_guide.md).
- **Service Layout**: Adheres to language-specific best practices (`src` for Python, standard Go layout for Go).

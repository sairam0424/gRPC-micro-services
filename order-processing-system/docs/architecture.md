# Architecture Documentation

## Overview
This system is composed of multiple microservices communicating via gRPC, adhering to industry standard repository structures.

### Components

1.  **API Gateway (Python FastAPI)**:
    *   **Structure**: Uses the `src` layout with `pyproject.toml`.
    *   **Responsibility**: REST endpoints, authentication (planned), and gRPC client for internal services. Now includes a **Tier-1 Bloom Filter** for catalog existence pre-filtering.
    *   **Path**: `api-gateway/src/app/`
2.  **Order Service (Go)**:
    *   **Structure**: Follows Standard Go Layout (`cmd/`, `internal/`, `pkg/`).
    *   **Responsibility**: Order business logic and gRPC server.
    *   **Path**: `order-service/cmd/server/`
3.  **Inventory Service (Python FastAPI)**:
    *   **Structure**: Uses the `src` layout with `pyproject.toml`.
    *   **Responsibility**: Manages product stock, implements **Event-Driven Caching** and a **Tier-2 Cuckoo Filter**.
    *   **Path**: `inventory-service/src/app/`

## Repository Structure

```text
.
├── api-gateway/            # Python FastAPI Gateway
│   ├── src/                # Source code
│   │   ├── app/            # Application logic
│   │   └── generated/      # Generated gRPC code
│   ├── pyproject.toml      # Dependency management
│   └── Dockerfile          # Containerization
├── order-service/          # Go Order Service
│   ├── cmd/                # Entry points
│   ├── internal/           # Private code
│   ├── pkg/                # Public/Shared code (generated gRPC)
│   ├── go.mod              # Dependency management
│   └── Dockerfile          # Containerization
├── proto/                  # Protobuf definitions
├── docs/                   # Documentation
├── Makefile                # Automation (code gen, etc)
└── docker-compose.yml      # Orchestration
```

```mermaid
graph TD
    Client[Web Browser] -->|REST| Proxy[Nginx Proxy]
    Proxy --> Gateway[API Gateway]
    Gateway -->|gRPC| Order[Order Service]
    Gateway -->|gRPC| Inventory[Inventory Service]
    
    subgraph "Event-Driven Caching"
        Inventory -->|Events| Kafka[(Kafka)]
        Kafka -->|Refresh| Inventory
        Inventory -->|Cache-Aside| Redis[(Redis Stack)]
    end
    
    subgraph "Observability & Management"
        Prometheus[(Prometheus)] --- Grafana[(Grafana)]
        Redis --- RedisInsight[RedisInsight]
        Redis --- RedisCommander[Redis Commander]
        Redis --- RedisExporter[Redis Exporter]
        RedisExporter --> Prometheus
    end
```

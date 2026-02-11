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
flowchart TD
    subgraph "Clients"
        Client[Web Browser]
    end

    subgraph "API Gateway Layer"
        Proxy[Nginx Proxy]
        Gateway[API Gateway]
    end

    subgraph "Inventory Service (Read/Write Routing)"
        Inventory[Inventory Service]
        ReadRouter{Read Router}
    end

    subgraph "Database Tier (Leader-Replica)"
        LeaderDB[(Postgres Leader\nWrites + Strong Reads)]
        ReplicaDB[(Postgres Replica\nEventual Reads)]
    end

    subgraph "CDC Pipeline"
        Debezium[Debezium Connector]
        Kafka[(Kafka)]
    end

    subgraph "Caching Tier"
        Redis[(Redis Stack)]
    end

    %% Flow
    Client -->|REST| Proxy
    Proxy --> Gateway
    Gateway -->|gRPC| Inventory
    
    Inventory -->|Write| LeaderDB
    Inventory -->|Strong Read| LeaderDB
    Inventory --> ReadRouter
    ReadRouter -->|Eventual Read| ReplicaDB

    %% Replication & CDC
    LeaderDB -->|Streaming Rep| ReplicaDB
    LeaderDB -->|WAL| Debezium
    Debezium -->|Events| Kafka
    Kafka -->|Update| Inventory
    
    %% Caching
    Inventory -->|Cache-Aside| Redis
```

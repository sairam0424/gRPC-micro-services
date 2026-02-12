# Architecture Documentation

## Overview
This system is composed of multiple microservices communicating via gRPC, adhering to industry standard repository structures.

### Components

1.  **Envoy Proxy**:
    *   **Responsibility**: L7 load balancer for gRPC and HTTP/2. Manages health checks, retries, and circuit breaking for the API Gateway cluster.
    *   **LB Policy**: Least Connection + Consistent Hashing.
2.  **API Gateway Cluster (Python FastAPI)**:
    *   **Structure**: Multiple replicas (e.g., `api-gateway-1`, `api-gateway-2`).
    *   **Responsibility**: REST endpoints, authentication, and gRPC hub. Includes Tier-1 Bloom Filter.
    **Tier-1 Bloom Filter** for catalog existence pre-filtering.
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
└── docker-compose.yml      ## Architecture (Raft Cluster + Multi-Replica CDC + Patroni HA)

```mermaid
flowchart TD
    subgraph "Clients"
        Client[Web Browser]
        Dashboard[Cluster Dashboard]
    end

    subgraph "Ingress & Load Balancing"
        Proxy[Nginx Proxy]
        Envoy[Envoy LB]
    end

    subgraph "API Gateway Cluster"
        GW1[API Gateway 1]
        GW2[API Gateway 2]
    end
 drum
    subgraph "High Availability Orchestration"
        HAProxy[HAProxy\nStable DB Endpoints]
        Patroni["Patroni\n(Node Manager)"]
        ETCD[(etcd - Raft Consensus)]
    end

    subgraph "Inventory Service (Raft Cluster)"
        Inventory[Inventory Service]
        MetricsRouter{Metric-Based Router}
    end

    subgraph "PostgreSQL Cluster (HA)"
        LeaderDB[(Postgres Leader\nWrites + Strong Reads)]
        Replica1[(Postgres Replica 1\nEventual Reads)]
        Replica2[(Postgres Replica 2\nEventual Reads)]
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
    Proxy --> Envoy
    Envoy --> GW1
    Envoy --> GW2
    GW1 -->|gRPC| Inventory
    GW2 -->|gRPC| Inventory
    Dashboard -->|Metrics| Gateway
    
    Inventory -->|Write| HAProxy:5432
    Inventory -->|Strong Read| HAProxy:5432
    Inventory --> MetricsRouter
    MetricsRouter -->|Lowest CPU| HAProxy:5433

    %% HA & Consensus
    HAProxy -->|Route to Leader| LeaderDB
    HAProxy -->|Route to Replicas| Replica1
    HAProxy -->|Route to Replicas| Replica2
    Patroni -->|Manage| LeaderDB
    Patroni -->|Manage| Replica1
    Patroni -->|Manage| Replica2
    Patroni <-->|Leader State| ETCD
    Inventory <-->|Service State| ETCD

    %% Replication & CDC
    LeaderDB -->|Streaming Rep| Replica1
    LeaderDB -->|WAL| Debezium
    Debezium -->|Events| Kafka
    Kafka -->|Async Rep| Inventory
    Inventory -->|Apply Changes| Replica2
    
    %% Caching
    Inventory -->|Cache-Aside| Redis
```

## Resilience & High Availability
The system now implements **Industry Standard High Availability**:
1.  **Raft Consensus**: Uses `etcd` for distributed leader election and cluster state management.
2.  **Multi-Replica Routing**: Metric-based routing (CPU, connections, health) ensures traffic is directed to the most optimal node.
3.  **Hybrid Replication**:
    *   **Native Streaming**: Replica 1 uses standard Postgres streaming replication.
    *   **Async CDC**: Replica 2 uses Kafka-based CDC (Debezium) for eventually consistent updates.

## Resilience Patterns

The **API Gateway** implements multiple resilience layers:
1.  **Rate Limiting**: Token Bucket algorithm with Redis for centralized limiting.
2.  **Load Shedding**: Automatic rejection of non-critical requests under high system stress.
3.  **Tier-1 Bloom Filter**: Prevents invalid catalog requests from hitting downstream services.

For more details, see [resilience.md](resilience.md).

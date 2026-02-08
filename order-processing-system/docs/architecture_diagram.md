# System Architecture Diagram - Order Processing System

This document provides a detailed view of the current system architecture and outlines strategies for handling scale.

## Architecture Overview

The system follows a microservices architecture using **gRPC** for efficient internal communication, **FastAPI** as an API Gateway, and **Nginx** as a reverse proxy.

### Current Architecture (Mermaid)

```mermaid
graph TD
    Client["Web Browser / Mobile"]
    
    subgraph "Infrastructure"
        Proxy["Nginx (Reverse Proxy)"]
    end
    
    subgraph "Microservices"
        WebClient["Web Client (Next.js)"]
        APIGateway["API Gateway (FastAPI)"]
        OrderService["Order Service (Go)"]
        InventoryService["Inventory Service (FastAPI)"]
    end
    
    subgraph "Storage"
        OrderInMemory["Order In-Memory (Map)"]
        InventoryDB[("PostgreSQL (Inventory)")]
    end
    
    %% Connections
    Client ---|HTTP/HTTPS| Proxy
    Proxy ---|Route: /| WebClient
    Proxy ---|Route: /api| APIGateway
    APIGateway ---|gRPC| OrderService
    APIGateway ---|gRPC| InventoryService
    OrderService ---|gRPC: ReserveStock| InventoryService
    OrderService ---|CRUD| OrderInMemory
    InventoryService ---|SQL| InventoryDB
    
    %% Styling
    style Client fill:#f9f,stroke:#333,stroke-width:2px
    style Proxy fill:#69f,stroke:#333,stroke-width:2px
    style APIGateway fill:#6f9,stroke:#333,stroke-width:2px
    style OrderService fill:#f96,stroke:#333,stroke-width:2px
    style InventoryService fill:#66ccff,stroke:#333,stroke-width:2px
    style InventoryDB fill:#ffcc00,stroke:#333
```

---

## Component Details

1.  **Nginx Proxy**: Acts as the entry point.
2.  **Web Client (Next.js)**: Modern dashboard for managing orders and viewing stock.
3.  **API Gateway (FastAPI)**: Routes external REST requests to internal gRPC services.
4.  **Order Service (Go)**: Manages business logic and coordinates with the Inventory Service.
5.  **Inventory Service (Python)**: Manages stock levels with ACID compliance via PostgreSQL.

---

## Scaling for Growth

- **Service Mesh**: Use Istio to manage gRPC traffic and retries.
- **Database Sharding**: As inventory grows, shard PostgreSQL by product category.
- **Caching**: Implement Redis in the Inventory Service for lightning-fast stock checks.

# Inventory Service

This service manages product stock for the Order Processing System.

## Features
- **FastAPI**: Provides a REST API for management and health checks.
- **gRPC**: High-performance internal API for order stock reservations.
- **PostgreSQL**: Managed persistence via Neon PostgreSQL.
- **ACID Compliance**: Uses transaction locks for atomic stock reservation.
- **Advanced Caching**: Redis-based Tier-1 cache for stock levels.
    - **Cache-Aside Strategy**: Reduces DB hits for frequent stock checks.
    - **Single-flight Pattern**: Prevents Cache Stampede by coalescing concurrent DB requests.
    - **Thundering Herd Protection**: TTL jitter to prevent simultaneous cache expirations.
    - **Cache Warming**: Background pipeline populates active items on startup.

## Configuration
The service is configured via environment variables in the project's root `.env` file.

- `DATABASE_URL`: Connection string for Neon PostgreSQL (must include `sslmode=require`).
- `INVENTORY_SERVICE_PORT`: Port for the FastAPI server (default: 8001).
- `GRPC_PORT`: Port for the gRPC server (default: 50052).
- `REDIS_HOST`: Host for the Redis server (default: `redis`).
- `REDIS_PORT`: Port for the Redis server (default: `6379`).
- `REDIS_PASSWORD`: Password for Redis (default: `bloompass`).

## Redis Management & Monitoring
- **RedisInsight**: `http://localhost:8003` (Native Redis UI)
- **Redis Commander**: `http://localhost:8081` (Web-based management)
- **Redis Exporter**: Metrics available on port `9121` (Scraped by Prometheus)

## Run Locally
Build and start using Docker from the project root:
```bash
docker compose up inventory-service
```

## Documentation
- [Neon Setup Guide](../docs/neon_setup.md)
- [Database Configuration](../docs/postgresql_config.md)

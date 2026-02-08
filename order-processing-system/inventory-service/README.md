# Inventory Service

This service manages product stock for the Order Processing System.

## Features
- **FastAPI**: Provides a REST API for management and health checks.
- **gRPC**: High-performance internal API for order stock reservations.
- **PostgreSQL**: Managed persistence via Neon PostgreSQL.
- **ACID Compliance**: Uses transaction locks for atomic stock reservation.

## Configuration
The service is configured via environment variables in the project's root `.env` file.

- `DATABASE_URL`: Connection string for Neon PostgreSQL (must include `sslmode=require`).
- `INVENTORY_SERVICE_PORT`: Port for the FastAPI server (default: 8001).
- `GRPC_PORT`: Port for the gRPC server (default: 50052).

## Run Locally
Build and start using Docker from the project root:
```bash
docker compose up inventory-service
```

## Documentation
- [Neon Setup Guide](../docs/neon_setup.md)
- [Database Configuration](../docs/postgresql_config.md)

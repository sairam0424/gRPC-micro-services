# PostgreSQL Configuration Guide - Inventory Service

This guide explains how the Inventory Service is configured to use PostgreSQL for persistent storage.

## Connection Details

The service uses **SQLAlchemy** with the **asyncpg** driver for asynchronous communication with **Neon PostgreSQL**.

- **URL**: Managed via `DATABASE_URL` in `.env`.
- **Driver**: `postgresql+asyncpg`
- **SSL**: Required (`sslmode=require`)
- **Setup**: See [Neon Setup Guide](./neon_setup.md) for detailed UI/Admin instructions.

## Table Schema

The `inventory` table is automatically created on service startup if it doesn't exist.

| Column | Type | Description |
| --- | --- | --- |
| `product_id` | String (PK) | Unique identifier for the product (e.g., PROD-001) |
| `name` | String | Human-readable name of the product |
| `quantity` | Integer | Current stock available |
| `updated_at` | DateTime | Timestamp of the last stock update |

## Initial Seeding

On the first run, the service seeds the following data:
- `PROD-001`: Laptop (10 units)
- `PROD-002`: Mouse (50 units)
- `PROD-003`: Keyboard (25 units)

## Critical: Atomic Operations

The service implements **SELECT FOR UPDATE** locks during stock reservation to prevent race conditions when multiple orders for the same product are placed simultaneously. This ensures strict inventory consistency.

```python
# snippet from main.py
result = await session.execute(
    select(InventoryItem)
    .where(InventoryItem.product_id == item_req.product_id)
    .with_for_update()
)
```

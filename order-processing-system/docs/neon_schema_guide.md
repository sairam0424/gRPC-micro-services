# Neon SQL Schema Guide

This guide provides the exact SQL statements required to manually create and manage the inventory schema in the Neon Web Console.

## 1. Create Inventory Table

Run this command in the Neon **SQL Editor** to initialize your database:

```sql
CREATE TABLE IF NOT EXISTS inventory (
    product_id VARCHAR(255) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    quantity INTEGER DEFAULT 0,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- Optimize for lookups during stock reservation
CREATE INDEX IF NOT EXISTS idx_inventory_product_id ON inventory(product_id);
```

## 2. Seed Initial Products

To quickly populate your store, run:

```sql
INSERT INTO inventory (product_id, name, quantity) 
VALUES 
    ('PROD-001', 'Laptop', 10),
    ('PROD-002', 'Mouse', 50),
    ('PROD-003', 'Keyboard', 25)
ON CONFLICT (product_id) DO NOTHING;
```

## 3. Useful Maintenance Queries

### Check Current Stock Levels
```sql
SELECT product_id, name, quantity, updated_at 
FROM inventory 
ORDER BY quantity ASC;
```

### Manually Increase Stock
```sql
UPDATE inventory 
SET quantity = quantity + 10 
WHERE product_id = 'PROD-001';
```

## 4. Connection Pooling (Neon Pooler)

The application is configured to connect via the Neon Pooler. 

- **Endpoint**: Ensure you are using the `-pooler` suffix in your host name.
- **SSL**: Always use `sslmode=require`.
- **Concurrency**: The app uses `pool_recycle` set to 1800 seconds to prevent session timeouts in serverless environments.

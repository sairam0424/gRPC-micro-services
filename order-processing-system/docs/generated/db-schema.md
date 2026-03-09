# Database Schema Snapshot

This is a documentation-level schema snapshot generated from current service models.

## Sources of Truth
- `order-service/internal/models/order.go`
- `order-service/internal/models/outbox.go`
- `order-service/internal/models/processed_event.go`
- `inventory-service/src/app/models.py`
- `media-service/src/app/models.py`
- `auth-service/src/app/models.py`

## Order Service Schema (GORM)

### `orders`
| Column | Type (logical) | Notes |
|---|---|---|
| `order_id` | string (PK) | External order identifier |
| `customer_id` | string (indexed) | Customer reference |
| `status` | string | Order state (pending/completed/failed/etc.) |
| `created_at` | timestamp | Audit timestamp |
| `updated_at` | timestamp | Audit timestamp |
| `media_ids` | text[] | Associated media references |

### `order_items`
| Column | Type (logical) | Notes |
|---|---|---|
| `id` | uint (PK) | Row identifier |
| `order_id` | string (indexed, FK logical) | Parent order reference |
| `product_id` | string | Product reference |
| `quantity` | uint32 | Ordered quantity |
| `price_cents` | int64 | Monetary amount in cents |

### `outbox`
| Column | Type (logical) | Notes |
|---|---|---|
| `id` | uint (PK) | Outbox row identifier |
| `aggregate_type` | string (indexed) | Aggregate kind |
| `aggregate_id` | string (indexed) | Aggregate identifier |
| `event_type` | string | Event semantic type |
| `payload` | bytea | Serialized protobuf payload |
| `created_at` | timestamp (indexed) | Outbox create time |
| `processed_at` | timestamp nullable (indexed) | Relay completion marker |

### `processed_events` (order-service)
| Column | Type (logical) | Notes |
|---|---|---|
| `event_id` | string (PK composite) | Event dedupe key |
| `service` | string (PK composite) | Consumer identity |
| `processed_at` | timestamp | Deduplication audit time |

## Inventory Service Schema (SQLAlchemy)

### `inventory`
| Column | Type (logical) | Notes |
|---|---|---|
| `product_id` | string (PK, indexed) | Product identifier |
| `name` | string | Product name |
| `quantity` | integer | Available stock |
| `media_id` | string nullable | Media reference |
| `updated_at` | timestamp | Last update timestamp |

### `processed_events` (inventory-service)
| Column | Type (logical) | Notes |
|---|---|---|
| `event_id` | string (PK, indexed) | Event dedupe key |
| `processed_at` | timestamp | Dedupe timestamp |
| `service` | string | Service marker |

## Media Service Schema (SQLAlchemy)

### `media_metadata`
| Column | Type (logical) | Notes |
|---|---|---|
| `media_id` | UUID (PK) | Media identifier |
| `entity_type` | string(50) | Domain owner type (`inventory`, `order`, etc.) |
| `entity_id` | string(100) | Domain owner identifier |
| `bucket_name` | string(100) | Object store bucket |
| `object_key` | string(500) | Object store key |
| `content_hash` | string(64) nullable | SHA-256 checksum |
| `content_type` | string(100) nullable | MIME type |
| `created_at` | timestamp | Create timestamp |
| `updated_at` | timestamp | Update timestamp |

## Auth Service Schema (SQLModel)

### `user`
| Column | Type (logical) | Notes |
|---|---|---|
| `id` | integer (PK) | User identifier |
| `username` | string (unique, indexed) | Login name |
| `email` | string (unique, indexed) | Contact/login email |
| `full_name` | string nullable | Display name |
| `hashed_password` | string | Password hash storage |
| `created_at` | datetime | Account creation time |
| `is_active` | boolean | Account status |

## Notes
- Physical schemas may differ across local vs cloud providers.
- Generated or migration-managed details should be validated against live DB introspection before destructive changes.

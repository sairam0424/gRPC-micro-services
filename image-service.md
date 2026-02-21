introduce:

🟢 Media Service (Blob Gateway)

Instead of:

Inventory Service → MinIO
Order Service → MinIO


Do:

Inventory → Media Service → MinIO
Order → Media Service → MinIO


This gives you:

✔ Storage abstraction
✔ Upload validation
✔ Metadata indexing
✔ Signed URL generation
✔ Image lifecycle management
✔ Saga-compatible operations
✔ Replay safety

MinIO becomes:

👉 Storage backend
NOT business logic dependency

2️⃣ WHERE THIS FITS IN YOUR PLANES
🟢 DATA PLANE

Media Service

MinIO

Inventory Service

Order Service

Handles:

Upload

Retrieval

Storage

Image metadata

🔵 CONTROL PLANE

Media Policy Store

Bucket configuration

Retention rules

Access policy

Lifecycle management

DLQ replay for upload events

MinIO config belongs here.

3️⃣ ARCHITECTURE FLOW
📤 Upload Flow
flowchart TD
    Client --> API Gateway
    API Gateway --> Media Service
    Media Service --> MinIO
    Media Service --> Kafka
    Kafka --> Inventory Service

4️⃣ MEDIA SERVICE RESPONSIBILITIES

This becomes your:

Blob Gateway Layer


It handles:

Responsibility	Why
Upload validation	Prevent corrupt files
Content-type check	Security
Image resizing (optional)	Performance
Metadata storage	Queryable
Signed URL generation	Secure access
Deduplication	Idempotency
Virus scanning (future)	Compliance
5️⃣ MINIO BUCKET DESIGN

Create:

inventory-images/
order-attachments/
user-uploads/
ml-artifacts/


Inside:

inventory-images/
   product-id/
      image-id.jpg

6️⃣ METADATA STORE DESIGN

Do NOT query MinIO for business logic.

Add:

media_metadata (
  media_id UUID,
  entity_type ENUM,
  entity_id UUID,
  object_key TEXT,
  bucket_name TEXT,
  uploaded_at
)


Example:

entity_type = PRODUCT
entity_id = PROD_123
object_key = inventory-images/PROD_123/abc.jpg


Inventory Service queries this DB, not MinIO.

7️⃣ SECURE ACCESS — SIGNED URL

Never expose MinIO publicly.

Media Service generates:

GET /media/{media_id}/signed-url


Uses MinIO SDK:

Returns:

pre-signed URL (5 min TTL)


Frontend uses that.

8️⃣ SAGA INTEGRATION

Image upload becomes:

Saga Step
Create Order Saga
  Step 1: Upload Image
  Step 2: Create Order
  Step 3: Reserve Inventory


If saga fails:

Compensation:

DeleteMediaCommand


Media Service deletes object from MinIO.

Now:

Uploads are transactional.

9️⃣ IDEMPOTENCY FOR UPLOADS

Use:

content_hash


If same image uploaded twice:

Skip upload

Return existing media_id

Avoids:

DLQ replay duplication

Retry duplication

🔟 EVENT-DRIVEN MEDIA FLOW

After upload:

Media Service emits:

media.uploaded.event


Inventory Service consumes:

Updates:

product.media_id


ClickHouse / Flink:

Tracks:

Image upload latency

Product completeness

User attachment usage

1️⃣1️⃣ FINAL ARCHITECTURE UPDATE
flowchart TD
    API --> MediaService
    MediaService --> MinIO
    MediaService --> MetadataDB

    MediaService --> Kafka
    Kafka --> InventoryService
    Kafka --> OrderService

    SagaOrchestrator --> MediaService

1️⃣2️⃣ REPLAY SAFETY

Replay upload event?

Inventory Service:

Already has:

media_id


Skip update.

Media Service:

Checks:

content_hash


No duplicate object.

1️⃣3️⃣ DATA MODEL IMPACT

Inventory:

product (
  product_id,
  media_id
)


Orders:

order_attachment (
  order_id,
  media_id
)


No binary in Postgres.

1️⃣4️⃣ BENEFITS

✔ Keeps DB lean
✔ Works with Saga
✔ Replay-safe
✔ Retry-safe
✔ Secure access
✔ Analytics ready
✔ Multi-tenant future-ready

FINAL RESULT

You now have:

Blob Storage Layer

Upload Transaction Support

Media Compensation Support

Secure Access

Metadata Index

Replay Safety

MinIO becomes:

→ Object store
Media Service becomes:

→ Media Control Layer
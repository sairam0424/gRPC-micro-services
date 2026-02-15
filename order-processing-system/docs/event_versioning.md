# Event Versioning & Schema Registry

The Order Processing System uses the **Confluent Schema Registry** to manage Protobuf schemas for all events published to Kafka. This ensures that producers and consumers can evolve independently while maintaining data integrity.

## Why Schema Registry?

In an event-driven system, data schemas are the "contract" between services.
- **Independence**: Producers (e.g., Go-based `order-service`) and Consumers (e.g., Python-based `inventory-service`) don't need to be redeployed at the same time.
- **Safety**: Prevents "poison pill" messages where a producer sends data that a consumer cannot parse.
- **Efficiency**: Protobuf messages are serialized as binary, and the schema is referenced by a small ID rather than being sent with every message.

## How it Works

1. **Schema Definition**: Schemas are defined as `.proto` files in the `proto/events/v1` directory.
2. **Registration**: When a service starts or a producer sends a message, it registers the schema with the Registry (if not already present).
3. **Serialization**: The producer packs the schema ID from the Registry into the binary payload.
4. **Deserialization**: The consumer reads the ID, fetches the schema from the Registry (and caches it), and then deserializes the payload.

## Schema Evolution Guidelines

We use **BACKWARD** compatibility by default. This means consumers using an older version of the schema can still read messages produced with a newer version.

### Safe Changes (Backward Compatible)
- **Add Fields**: New fields must be given a new, unique tag number. Old consumers will simply ignore the new field.
- **Delete Fields**: You can stop sending a field, but **never reuse the tag number**. Mark it as `reserved`.

### Unsafe Changes (Breaking)
- **Renaming Tags**: Never change the numeric tag of a field.
- **Changing Types**: Changing a `string` to an `int32` for the same tag is a breaking change.
- **Required Fields**: Protobuf 3 does not have explicit `required` fields; all are optional. Do not assume a field will always be present.

## Viewing Schemas

You can view the current registered schemas and versions via the **Kafka UI**:
- Access: `http://localhost:8080`
- Section: **Schema Registry**

## Implementation Details

### Go (order-service)
Uses `confluent-kafka-go` with the Protobuf serializer.
- Producer configuration includes `schema.registry.url`.
- Protobuf generated code is used for type-safe message creation.

### Python (inventory-service)
Uses `confluent-kafka[protobuf]` with the `ProtobufDeserializer`.
- Configured via `SCHEMA_REGISTRY_URL` environment variable.
- Uses `ProtobufDeserializer` to automatically fetch schemas and validate incoming messages.

## Operational Workflow

1. Modify `.proto` files in `proto/events/v1/`.
2. Run `make generate` to update Go and Python code.
3. Update producer/consumer logic.
4. Test locally using `make up-dev`.

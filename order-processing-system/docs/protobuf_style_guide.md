# Protobuf Style Guide

This project follows the official [Google Protobuf Style Guide](https://protobuf.dev/programming-guides/style/).

## Standard File Formatting
- **Line Length**: Keep lines to 80 characters where possible.
- **Indentation**: Use **2 spaces** for indentation.
- **Strings**: Prefer double quotes for string literals.

## File Structure
- **Naming**: Files should be named `lower_snake_case.proto`.
- **Order**:
  1. License header
  2. File overview
  3. Syntax (`syntax = "proto3";`)
  4. Package (`package order.v1;`)
  5. Imports (sorted)
  6. File options (`option go_package = ...;`)
  7. Service and Message definitions

## Naming Conventions

### Packages
- Use dot-delimited `lower_snake_case` names.
- Example: `package order.v1;`

### Messages
- Use **TitleCase** (PascalCase) for message names.
- Example: `message CreateOrderRequest { ... }`

### Fields
- Use **snake_case** for field names.
- Use plural names for repeated fields.
- Example: `string customer_id = 1;` or `repeated OrderItem items = 2;`

### Enums
- Use **TitleCase** for enum type names.
- Use **UPPER_SNAKE_CASE** for enum values.
- **Prefix**: Every value must be prefixed with the enum name (converted to UPPER_SNAKE_CASE).
- **Default**: The first value (0) must be `_UNSPECIFIED`.
- Example:
  ```proto
  enum OrderStatus {
    ORDER_STATUS_UNSPECIFIED = 0;
    ORDER_STATUS_PENDING = 1;
    ORDER_STATUS_COMPLETED = 2;
  }
  ```

### Services
- Use **TitleCase** for both service and method names.
- Naming format: `rpc [MethodName]([MethodName]Request) returns ([MethodName]Response);`
- Example: `rpc CreateOrder(CreateOrderRequest) returns (CreateOrderResponse);`

# Setup Guide

## Prerequisites
- Docker & Docker Compose
- Python 3.10+ (for local development)
- Go 1.20+ (for local development)
- `protoc` (Protocol Buffers Compiler)

## Option 1: Using Docker (Recommended)

This is the easiest way to run the entire system including gRPC generation.

### 1. Build and Run
```bash
docker-compose up --build
```

### 2. Clean Up
```bash
docker-compose down
```

## Option 2: Local Development

### 1. Generate gRPC Code
Use the provided Makefile to generate code for both Python and Go:
```bash
make generate
```

### 2. Python API Gateway
```bash
cd api-gateway
pip install .
python src/app/main.py
```

### 3. Go Order Service
```bash
cd order-service
go mod tidy
go run cmd/server/main.go
```

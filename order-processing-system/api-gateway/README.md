# API Gateway (Python FastAPI)

This service acts as the entry point for external clients, exposing REST endpoints and communicating with internal services via gRPC.

## Key Features
- **FastAPI**: High-performance REST framework.
- **gRPC Client**: Communicates with the Order Service.
- **Modern Structure**: Follows the `src` layout.

## Local Setup

### 1. Install Dependencies
```bash
cd api-gateway
pip install .
```

### 2. Run the Service
```bash
python src/app/main.py
```

## Docker
The Dockerfile uses a multi-stage build for a slim production-ready image.
```bash
docker build -t api-gateway .
```

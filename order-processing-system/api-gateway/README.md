# API Gateway (Python FastAPI)

This service acts as the entry point for external clients, exposing REST endpoints and communicating with internal services via gRPC.

## Local Setup

### Option 1: Using `uv` (Recommended)

`uv` is an extremely fast Python package manager that handles virtual environments automatically.

#### macOS / Linux
```bash
cd api-gateway
uv venv
source .venv/bin/activate
uv pip install -e .
uvicorn src.app.main:app --reload
```

#### Windows (PowerShell)
```bash
cd api-gateway
uv venv
.\.venv\Scripts\Activate.ps1
uv pip install -e .
uvicorn src.app.main:app --reload
```

---

### Option 2: Using standard `pip`

#### macOS / Linux
```bash
cd api-gateway
python3 -m venv venv
source venv/bin/activate
pip install -e .
python3 -m uvicorn src.app.main:app --reload
```

#### Windows (PowerShell)
```bash
cd api-gateway
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -e .
python -m uvicorn src.app.main:app --reload
```

---

## Docker Setup

### 1. Build the Image
From the `api-gateway` directory:
```bash
docker build -t api-gateway .
```

### 2. Run the Container (Standard Mode)
```bash
docker run -p 8000:8000 api-gateway
```

### 3. Run in Watch Mode (Hot-Reloading)
From the **project root**, run:
```bash
docker-compose -f docker-compose.dev.yml up api-gateway
```
*Changes to `src/` will trigger an automatic reload.*

---

## Advanced Docker Commands

### View Logs
```bash
# Follow logs in real-time
docker logs -f [container_id_or_name]
```

### Interactive Shell
```bash
# Access the container's shell
docker exec -it [container_id_or_name] /bin/sh
```

### Lifecycle Management
```bash
# Stop a container
docker stop [container_id_or_name]

# Remove a container
docker rm [container_id_or_name]

# List running containers
docker ps
```

## Troubleshooting
- **ModuleNotFoundError**: Ensure you are running `uvicorn` from within the activated virtual environment or using the full path to the executable (e.g., `./venv/bin/uvicorn`).
- **Python Version**: This project requires Python 3.10+. Check your version with `python --version`.

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

### 2. Run the Container
```bash
docker run -p 8000:8000 api-gateway
```

## Troubleshooting
- **ModuleNotFoundError**: Ensure you are running `uvicorn` from within the activated virtual environment or using the full path to the executable (e.g., `./venv/bin/uvicorn`).
- **Python Version**: This project requires Python 3.10+. Check your version with `python --version`.

FROM python:3.10-slim AS builder

WORKDIR /app
COPY pyproject.toml .
RUN mkdir src
COPY src/ ./src/

# Install protobuf to fix incompatibility
RUN pip install --no-cache-dir protobuf==4.25.1 && \
    pip install --no-cache-dir .

FROM python:3.10-slim

WORKDIR /app
COPY --from=builder /usr/local/lib/python3.10/site-packages /usr/local/lib/python3.10/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

COPY src/ ./src/

# FastAPI port
EXPOSE 8001
# gRPC port
EXPOSE 50052

CMD ["python", "src/app/main.py"]

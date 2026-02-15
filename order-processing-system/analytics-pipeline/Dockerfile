# Build stage for connectors
FROM alpine:3.19 AS connector-builder

RUN apk add --no-cache wget

WORKDIR /opt/flink/lib

# Download Flink S3 and Kafka connectors in parallel
RUN wget https://repo.maven.apache.org/maven2/org/apache/flink/flink-s3-fs-hadoop/1.18.1/flink-s3-fs-hadoop-1.18.1.jar && \
    wget https://repo.maven.apache.org/maven2/org/apache/flink/flink-sql-connector-kafka/3.0.1-1.18/flink-sql-connector-kafka-3.0.1-1.18.jar && \
    wget https://repo.maven.apache.org/maven2/org/apache/flink/flink-connector-jdbc/3.1.2-1.18/flink-connector-jdbc-3.1.2-1.18.jar && \
    wget https://repo.maven.apache.org/maven2/org/apache/flink/flink-sql-connector-elasticsearch7/3.0.1-1.17/flink-sql-connector-elasticsearch7-3.0.1-1.17.jar

# Final stage
FROM flink:1.18.1-java11

# Install uv for lightning fast builds
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Install python3 and build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    python3-dev \
    openjdk-11-jdk-headless \
    gcc \
    g++ \
    build-essential \
    protobuf-compiler \
    && rm -rf /var/lib/apt/lists/*

# Fix JAVA_HOME for pemja/pyflink build (works for both amd64 and arm64)
RUN ln -s /usr/lib/jvm/java-11-openjdk-$(dpkg --print-architecture) /usr/lib/jvm/java-11-openjdk
ENV JAVA_HOME=/usr/lib/jvm/java-11-openjdk

# Set python3 as default python
RUN ln -sf /usr/bin/python3 /usr/bin/python

# Copy connectors from builder stage
COPY --from=connector-builder /opt/flink/lib/*.jar /opt/flink/lib/

# Install dependencies into a virtualenv using uv
RUN uv venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /app
COPY requirements.txt .
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install -r requirements.txt

COPY src/ /app/src/

# Command to run the Flink job
CMD ["python", "src/main.py"]

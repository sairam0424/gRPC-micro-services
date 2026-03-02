# Build stage for connectors
FROM alpine:3.20 AS connector-builder

RUN apk add --no-cache wget

WORKDIR /opt/flink/lib

# Download Flink S3 and Kafka connectors in parallel
RUN wget https://repo.maven.apache.org/maven2/org/apache/flink/flink-s3-fs-hadoop/1.18.1/flink-s3-fs-hadoop-1.18.1.jar && \
    wget https://repo.maven.apache.org/maven2/org/apache/flink/flink-sql-connector-kafka/3.0.1-1.18/flink-sql-connector-kafka-3.0.1-1.18.jar && \
    wget https://repo.maven.apache.org/maven2/org/apache/flink/flink-connector-jdbc/3.1.2-1.18/flink-connector-jdbc-3.1.2-1.18.jar && \
    wget https://repo.maven.apache.org/maven2/org/apache/flink/flink-sql-connector-elasticsearch7/3.0.1-1.17/flink-sql-connector-elasticsearch7-3.0.1-1.17.jar

# Final stage
FROM flink:1.18.1-java17

# Pin uv version
COPY --from=ghcr.io/astral-sh/uv:0.5.11 /uv /bin/uv

# Install python3 and build dependencies
# Upgrade system packages and use Java 17 tools
RUN apt-get update && apt-get upgrade -y && \
    apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    python3-dev \
    openjdk-17-jdk-headless \
    gcc \
    g++ \
    build-essential \
    protobuf-compiler \
    && rm -rf /var/lib/apt/lists/*

# Fix JAVA_HOME for Java 17
RUN ln -s /usr/lib/jvm/java-17-openjdk-$(dpkg --print-architecture) /usr/lib/jvm/java-17-openjdk
ENV JAVA_HOME="/usr/lib/jvm/java-17-openjdk"

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

# Ensure flink user owns the app directory
RUN chown -R flink:flink /app

# Run as the default flink user
USER flink

# Command to run the Flink job
CMD ["python", "src/main.py"]


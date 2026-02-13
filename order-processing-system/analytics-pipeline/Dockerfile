FROM flink:1.18.1-java11

# Install python3 and pip
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-dev \
    openjdk-11-jdk \
    && rm -rf /var/lib/apt/lists/*

# Set JAVA_HOME (required for pemja)
ENV JAVA_HOME=/usr/lib/jvm/java-11-openjdk-arm64
# Note: For x86 it might be /usr/lib/jvm/java-11-openjdk-amd64
# To be safe, we can use a glob or find it dynamically, but usually arm64 is what user is on (mac m1/m2)

# Set python3 as default python
RUN ln -s /usr/bin/python3 /usr/bin/python

# Install PyFlink and other dependencies
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

# Download Flink S3 and Kafka connectors
RUN wget -P /opt/flink/lib https://repo.maven.apache.org/maven2/org/apache/flink/flink-s3-fs-hadoop/1.18.1/flink-s3-fs-hadoop-1.18.1.jar
RUN wget -P /opt/flink/lib https://repo.maven.apache.org/maven2/org/apache/flink/flink-sql-connector-kafka/3.0.1-1.18/flink-sql-connector-kafka-3.0.1-1.18.jar
RUN wget -P /opt/flink/lib https://repo.maven.apache.org/maven2/org/apache/flink/flink-connector-jdbc/3.1.2-1.18/flink-connector-jdbc-3.1.2-1.18.jar
RUN wget -P /opt/flink/lib https://repo1.maven.org/maven2/com/clickhouse/flink/flink-connector-clickhouse-1.17/0.1.3/flink-connector-clickhouse-1.17-0.1.3-all.jar
RUN wget -P /opt/flink/lib https://repo.maven.apache.org/maven2/org/apache/flink/flink-sql-connector-elasticsearch7/3.0.1-1.17/flink-sql-connector-elasticsearch7-3.0.1-1.17.jar

WORKDIR /app
COPY src/ /app/src/

# Command to run the Flink job (this will be handled by JobManager, but we can put a placeholder)
CMD ["python", "src/main.py"]

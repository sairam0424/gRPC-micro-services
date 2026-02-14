import os
import json
import logging
import duckdb
import boto3
from botocore.client import Config
from pyflink.common import WatermarkStrategy, Configuration
from pyflink.table import StreamTableEnvironment, EnvironmentSettings, TableDescriptor, Schema, DataTypes

# Configure Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def setup_minio():
    """Ensure required buckets exist using MINIO_ROOT credentials."""
    endpoint = os.getenv("S3_ENDPOINT", "http://minio:9000")
    access_key = os.getenv("MINIO_ROOT_USER", "admin")
    secret_key = os.getenv("MINIO_ROOT_PASSWORD", "strongpassword123")
    
    logger.info(f"Connecting to MinIO at {endpoint} as ROOT to ensure buckets exist...")
    s3 = boto3.client(
        's3',
        endpoint_url=endpoint,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        config=Config(signature_version='s3v4'),
        region_name='us-east-1'
    )
    
    buckets = ['flink-checkpoints', 'ml-models', 'feature-store', 'raw-events']
    for bucket in buckets:
        try:
            s3.head_bucket(Bucket=bucket)
            logger.info(f"Bucket '{bucket}' already exists.")
        except:
            logger.info(f"Creating bucket '{bucket}'...")
            s3.create_bucket(Bucket=bucket)

def main():
    logger.info("Starting High-Performance Analytics Pipeline...")
    
    # 0. Setup Infrastructure (Infrastructure setup usually requires root/admin)
    setup_minio()
    
    # Environment Setup
    # Settings for cluster execution to ensure visibility in Flink UI
    config = Configuration()
    config.set_string("jobmanager.rpc.address", os.getenv("FLINK_JOBMANAGER_HOST", "flink-jobmanager"))
    config.set_string("rest.address", os.getenv("FLINK_JOBMANAGER_HOST", "flink-jobmanager"))
    config.set_integer("rest.port", 8081)
    
    settings = EnvironmentSettings.new_instance().in_streaming_mode().with_configuration(config).build()
    t_env = StreamTableEnvironment.create(environment_settings=settings)
    
    # Configuration for S3 State Backend & Checkpointing (Use Service Account)
    conf = t_env.get_config().get_configuration()
    conf.set_string("s3.endpoint", os.getenv("S3_ENDPOINT", "http://minio:9000"))
    conf.set_string("s3.access-key", os.getenv("S3_ACCESS_KEY", "flink-user"))
    conf.set_string("s3.secret-key", os.getenv("S3_SECRET_KEY", "somepassword"))
    conf.set_string("s3.path.style.access", "true")
    conf.set_string("state.backend", "rocksdb")
    # File-system storage for Job/Task Manager logs is handled by Flink's log4j configuration
    # but we ensure durability through s3 for checkpoints
    conf.set_string("state.checkpoints.dir", "s3://flink-checkpoints/checkpoints")
    conf.set_string("execution.checkpointing.mode", "EXACTLY_ONCE")
    conf.set_string("execution.checkpointing.interval", "60s")

    kafka_brokers = os.getenv("KAFKA_BROKERS", "kafka:29092")

    # 1. Kafka Source Table
    t_env.execute_sql(f"""
        CREATE TABLE order_events (
            order_id STRING,
            customer_id STRING,
            event_type STRING,
            status STRING,
            message STRING,
            event_time TIMESTAMP(3) METADATA FROM 'timestamp',
            WATERMARK FOR event_time AS event_time - INTERVAL '5' SECOND
        ) WITH (
            'connector' = 'kafka',
            'topic' = 'order-events',
            'properties.bootstrap.servers' = '{kafka_brokers}',
            'properties.group.id' = 'analytics-group',
            'scan.startup.mode' = 'earliest-offset',
            'format' = 'json'
        )
    """)

    # 2. ClickHouse Sink (Analytics) - Securely connected to ClickHouse Cloud
    clickhouse_host = os.getenv("CLICKHOUSE_CLOUD_HOST", "clickhouse")
    clickhouse_port = os.getenv("CLICKHOUSE_CLOUD_PORT", "8123")
    clickhouse_user = os.getenv("CLICKHOUSE_CLOUD_USER", "default")
    clickhouse_password = os.getenv("CLICKHOUSE_CLOUD_PASSWORD", "")
    
    use_ssl = "true" if clickhouse_port == "8443" else "false"

    # Using the official ClickHouse Flink Connector
    t_env.execute_sql(f"""
        CREATE TABLE clickhouse_sink (
            customer_id STRING,
            order_count BIGINT,
            last_event_time TIMESTAMP(3)
        ) WITH (
            'connector' = 'clickhouse',
            'url' = '{clickhouse_host}:{clickhouse_port}',
            'username' = '{clickhouse_user}',
            'password' = '{clickhouse_password}',
            'database-name' = 'default',
            'table-name' = 'order_analytics',
            'use-ssl' = '{use_ssl}'
        )
    """)

    # 3. Elasticsearch Sink (Search Index) - Securely connected to Elasticsearch Cloud
    es_endpoint = os.getenv("ELASTICSEARCH_CLOUD_ENDPOINT", "http://elasticsearch:9200")
    es_api_key = os.getenv("ELASTICSEARCH_CLOUD_API_KEY", "")

    # For Elaticsearch Cloud, we use the API Key in the 'password' field if using a standard connector 
    # that supports basic auth over HTTPS, or customize if using a specific cloud connector.
    # Note: 'elasticsearch-7' connector properties might vary, using API Key as password is a common pattern for cloud.
    t_env.execute_sql(f"""
        CREATE TABLE elasticsearch_sink (
            order_id STRING,
            customer_id STRING,
            status STRING,
            message STRING
        ) WITH (
            'connector' = 'elasticsearch-7',
            'hosts' = '{es_endpoint}',
            'index' = 'orders',
            'password' = '{es_api_key}'
        )
    """)

    # 4. DuckDB / ML Sink placeholder
    # For DuckDB, we can use a filesystem sink that writes to Parquet, which DuckDB/Feast can consume
    t_env.execute_sql("""
        CREATE TABLE ml_features_sink (
            customer_id STRING,
            order_id STRING,
            status STRING,
            event_time TIMESTAMP(3)
        ) WITH (
            'connector' = 'filesystem',
            'path' = 's3://flink-features/ml_data',
            'format' = 'parquet'
        )
    """)

    # 5. Dead Letter Queue Sink (Kafka)
    t_env.execute_sql(f"""
        CREATE TABLE analytics_dlq (
            order_id STRING,
            customer_id STRING,
            event_type STRING,
            error_message STRING
        ) WITH (
            'connector' = 'kafka',
            'topic' = 'analytics.dlq',
            'properties.bootstrap.servers' = '{kafka_brokers}',
            'format' = 'json'
        )
    """)

    # --- Executing Pipeline via StatementSet for Unified Visibility ---
    statement_set = t_env.create_statement_set()

    # Add ClickHouse Sink
    statement_set.add_insert_sql("""
        INSERT INTO clickhouse_sink
        SELECT customer_id, COUNT(order_id), MAX(event_time)
        FROM order_events
        GROUP BY customer_id
    """)

    # Add Elasticsearch Sink
    statement_set.add_insert_sql("""
        INSERT INTO elasticsearch_sink
        SELECT order_id, customer_id, status, message
        FROM order_events
    """)

    # Add ML Store Sink
    statement_set.add_insert_sql("""
        INSERT INTO ml_features_sink
        SELECT customer_id, order_id, status, event_time
        FROM order_events
        WHERE order_id IS NOT NULL AND customer_id IS NOT NULL
    """)

    # Add Dead Letter Queue Sink for invalid events
    statement_set.add_insert_sql("""
        INSERT INTO analytics_dlq
        SELECT order_id, customer_id, event_type, 'Missing order_id or customer_id' as error_message
        FROM order_events
        WHERE order_id IS NULL OR customer_id IS NULL
    """)

    logger.info("Submitting unified Flink job: Order Analytics Pipeline")
    statement_set.execute().wait() # Wait for submission (not necessarily job completion in streaming)

if __name__ == "__main__":
    main()

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

import urllib.request
import time

def check_connectivity(url, timeout=5, retries=3, delay=5):
    """Check if a URL is reachable with retries and delay."""
    if not url.startswith('http'):
        url = f"http://{url}"
        
    for attempt in range(1, retries + 1):
        try:
            logger.info(f"Connectivity check attempt {attempt}/{retries} for {url}...")
            urllib.request.urlopen(url, timeout=timeout)
            return True
        except Exception as e:
            logger.warning(f"Attempt {attempt}/{retries} failed for {url}: {e}")
            if attempt < retries:
                logger.info(f"Retrying in {delay} seconds...")
                time.sleep(delay)
    return False

def setup_minio():
    """Ensure required buckets exist using MINIO_ROOT credentials."""
    endpoint = os.getenv("S3_ENDPOINT", "http://minio:9000")
    access_key = os.getenv("MINIO_ROOT_USER", "admin")
    secret_key = os.getenv("MINIO_ROOT_PASSWORD", "strongpassword123")
    
    logger.info(f"Connecting to MinIO at {endpoint} as ROOT to ensure buckets exist (Timeout: 10s)...")
    try:
        s3 = boto3.client(
            's3',
            endpoint_url=endpoint,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            config=Config(signature_version='s3v4', connect_timeout=10, retries={'max_attempts': 2}),
            region_name='us-east-1'
        )
        
        buckets = ['flink-checkpoints', 'ml-models', 'feature-store', 'raw-events']
        for bucket in buckets:
            try:
                s3.head_bucket(Bucket=bucket)
                logger.info(f"Bucket '{bucket}' already exists.")
            except Exception as e:
                logger.info(f"Creating bucket '{bucket}' because head_bucket failed: {e}")
                try:
                    s3.create_bucket(Bucket=bucket)
                except Exception as create_err:
                    logger.error(f"Failed to create bucket {bucket}: {create_err}")
    except Exception as e:
        logger.error(f"Could not connect to MinIO during startup: {e}. Flink checkpointing might fail if buckets are missing.")

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
    s3_endpoint = os.getenv("S3_ENDPOINT", "http://minio:9000")
    s3_access_key = os.getenv("S3_ACCESS_KEY", "flink-user")
    s3_secret_key = os.getenv("S3_SECRET_KEY", "somepassword")

    # Flink standard S3 properties
    conf.set_string("s3.endpoint", s3_endpoint)
    conf.set_string("s3.access-key", s3_access_key)
    conf.set_string("s3.secret-key", s3_secret_key)
    conf.set_string("s3.path.style.access", "true")
    
    # Hadoop S3A properties for filesystem connector
    conf.set_string("fs.s3a.endpoint", s3_endpoint)
    conf.set_string("fs.s3a.access.key", s3_access_key)
    conf.set_string("fs.s3a.secret.key", s3_secret_key)
    conf.set_string("fs.s3a.path.style.access", "true")
    conf.set_string("fs.s3a.connection.ssl.enabled", "false")
    conf.set_string("fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem")
    # Force s3:// to also use S3A to avoid missing credentials errors from default client
    conf.set_string("fs.s3.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem")


    conf.set_string("state.backend", "rocksdb")
    # File-system storage for Job/Task Manager logs is handled by Flink's log4j configuration
    # but we ensure durability through s3 for checkpoints
    # conf.set_string("state.checkpoints.dir", "s3a://flink-checkpoints/checkpoints")
    # conf.set_string("execution.checkpointing.mode", "EXACTLY_ONCE")
    # conf.set_string("execution.checkpointing.interval", "60s")

    kafka_brokers = os.getenv("KAFKA_BROKERS", "kafka:29092")

    # 1. Kafka Source Table (Raw format to handle Protobuf with Confluent header)
    t_env.execute_sql(f"""
        CREATE TABLE order_events_raw (
            payload BYTES,
            event_time TIMESTAMP(3) METADATA FROM 'timestamp',
            WATERMARK FOR event_time AS event_time - INTERVAL '5' SECOND
        ) WITH (
            'connector' = 'kafka',
            'topic' = 'order-events',
            'properties.bootstrap.servers' = '{kafka_brokers}',
            'properties.group.id' = 'analytics-group',
            'scan.startup.mode' = 'earliest-offset',
            'format' = 'raw'
        )
    """)

    # --- Python UDF for Protobuf Parsing ---
    from pyflink.table.expressions import col
    from pyflink.table.udf import udf

    @udf(result_type=DataTypes.ROW([
        DataTypes.FIELD("order_id", DataTypes.STRING()),
        DataTypes.FIELD("customer_id", DataTypes.STRING()),
        DataTypes.FIELD("event_type", DataTypes.STRING()),
        DataTypes.FIELD("status", DataTypes.STRING()),
        DataTypes.FIELD("message", DataTypes.STRING())
    ]))
    def parse_protobuf_event(data):
        from generated.events.v1 import events_pb2
        try:
            # Strip 5-byte Confluent header: [magic_byte][schema_id]
            if len(data) < 5:
                return None
            protobuf_payload = data[5:]
            event = events_pb2.OrderCreatedEvent()
            event.ParseFromString(protobuf_payload)
            return (
                event.order_id,
                event.customer_id,
                event.event_type,
                event.status,
                event.message
            )
        except Exception as e:
            logger.error(f"UDF Error parsing protobuf: {e}")
            return None

    t_env.create_temporary_system_function("parse_protobuf_event", parse_protobuf_event)

    # Create a view that uses the UDF to parse the raw payload
    t_env.execute_sql("""
        CREATE VIEW order_events AS
        SELECT 
            parsed.order_id,
            parsed.customer_id,
            parsed.event_type,
            parsed.status,
            parsed.message,
            event_time
        FROM (
            SELECT parse_protobuf_event(payload) as parsed, event_time
            FROM order_events_raw
        )
    """)

    # 3. Elasticsearch Sink (Local or Cloud)
    es_host = os.getenv("ELASTICSEARCH_HOST", "elasticsearch")
    es_port = os.getenv("ELASTICSEARCH_PORT", "9200")
    es_cloud_endpoint = os.getenv("ELASTICSEARCH_CLOUD_ENDPOINT", "")
    es_api_key = os.getenv("ELASTICSEARCH_CLOUD_API_KEY", "")

    es_sink_config = None
    
    # Try Cloud if configured and reachable
    if es_api_key and es_cloud_endpoint:
        logger.info(f"Preference: Cloud Elasticsearch at {es_cloud_endpoint}. Starting connectivity check with retries...")
        if check_connectivity(es_cloud_endpoint, timeout=10, retries=3, delay=5):
            logger.info("Cloud Elasticsearch is reachable. Using Cloud sink.")
            es_sink_config = f"""
                'connector' = 'elasticsearch-7',
                'hosts' = '{es_cloud_endpoint}',
                'username' = 'apiKey',
                'password' = '{es_api_key}',
                'index' = 'order_analytics'
            """
        else:
            logger.error("Cloud Elasticsearch unreachable after all retries. Falling back to local Elasticsearch.")

    # Fallback to local if Cloud failed or not configured
    if not es_sink_config:
        local_url = f"http://{es_host}:{es_port}"
        logger.info(f"Configuring Elasticsearch sink for LOCAL at {local_url}")
        es_sink_config = f"""
            'connector' = 'elasticsearch-7',
            'hosts' = '{local_url}',
            'index' = 'order_analytics'
        """

    try:
        t_env.execute_sql(f"""
            CREATE TABLE elasticsearch_sink (
                order_id STRING,
                customer_id STRING,
                status STRING,
                message STRING,
                PRIMARY KEY (order_id) NOT ENFORCED
            ) WITH (
                {es_sink_config}
            )
        """)
        logger.info("Elasticsearch sink created successfully.")
    except Exception as e:
        logger.warning(f"Could not create Elasticsearch sink: {e}. Skipping...")

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
    
    active_sinks = set(t_env.list_tables())

    # Elasticsearch Sink Insertion
    if "elasticsearch_sink" in active_sinks:
        try:
            logger.info("Adding Elasticsearch insertion to statement set (with null order_id filter).")
            statement_set.add_insert_sql("""
                INSERT INTO elasticsearch_sink
                SELECT order_id, customer_id, status, message
                FROM order_events
                WHERE order_id IS NOT NULL
            """)
        except Exception as e:
            logger.warning(f"Error adding Elasticsearch insertion: {e}")

    # Add Dead Letter Queue Sink for invalid events
    if "analytics_dlq" in active_sinks:
        statement_set.add_insert_sql("""
            INSERT INTO analytics_dlq
            SELECT order_id, customer_id, event_type, 'Missing order_id or customer_id' as error_message
            FROM order_events
            WHERE order_id IS NULL OR customer_id IS NULL
        """)

    logger.info("Submitting unified Flink job: Order Analytics Pipeline")
    try:
        statement_set.execute().wait() # Wait for submission
    except Exception as e:
        logger.error(f"Failed to execute Flink job: {e}")
        logger.info(f"Available tables at failure: {t_env.list_tables()}")
        raise e

if __name__ == "__main__":
    main()

if __name__ == "__main__":
    main()

import os
from minio import Minio
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)

class MinioManager:
    def __init__(self):
        self.endpoint = os.getenv("MINIO_ENDPOINT", "minio:9000").replace("http://", "").replace("https://", "")
        self.public_endpoint = os.getenv("MINIO_PUBLIC_ENDPOINT", "http://localhost:9000")
        
        # Parse public endpoint for its hostname/port for pre-signing
        public_url_clean = self.public_endpoint.replace("http://", "").replace("https://", "").rstrip('/')
        
        self.access_key = os.getenv("MINIO_ROOT_USER", "admin")
        self.secret_key = os.getenv("MINIO_ROOT_PASSWORD", "strongpassword123")
        self.secure = os.getenv("MINIO_SECURE", "False").lower() == "true"
        self.public_secure = self.public_endpoint.startswith("https")
        
        # Internal client for operations like delete
        self.client = Minio(
            self.endpoint,
            access_key=self.access_key,
            secret_key=self.secret_key,
            secure=self.secure
        )
        
        # Public client specifically for generating pre-signed URLs
        # This ensures the 'Host' header in the signature matches the browser's view
        self.public_client = Minio(
            public_url_clean,
            access_key=self.access_key,
            secret_key=self.secret_key,
            secure=self.public_secure
        )

    def generate_upload_url(self, bucket_name: str, object_name: str, expires_in_minutes: int = 15):
        """Generate a pre-signed URL for uploading (PUT)"""
        try:
            return self.public_client.presigned_put_object(
                bucket_name,
                object_name,
                expires=timedelta(minutes=expires_in_minutes)
            )
        except Exception as e:
            logger.error(f"Error generating upload URL: {e}")
            raise

    def generate_view_url(self, bucket_name: str, object_name: str, expires_in_minutes: int = 60):
        """Generate a pre-signed URL for viewing (GET)"""
        try:
            return self.public_client.presigned_get_object(
                bucket_name,
                object_name,
                expires=timedelta(minutes=expires_in_minutes)
            )
        except Exception as e:
            logger.error(f"Error generating view URL: {e}")
            raise

    def delete_object(self, bucket_name: str, object_name: str):
        """Delete an object from MinIO"""
        try:
            self.client.remove_object(bucket_name, object_name)
        except Exception as e:
            logger.error(f"Error deleting object: {e}")
            raise

minio_manager = MinioManager()

"""Cloudflare R2 Object Storage client using S3 API protocol for scalable, zero-egress media hosting."""

import os
import logging
from dotenv import load_dotenv

load_dotenv()


class R2StorageService:
    """Manages cloud asset uploads and public URL resolution on Cloudflare R2."""

    def __init__(self):
        self.account_id = (
            os.getenv("R2_ACCOUNT_ID")
            or os.getenv("CLOUDFLARE_R2_ACCOUNT_ID")
            or os.getenv("CLOUDFLARE_ACCOUNT_ID")
            or ""
        ).strip()
        self.access_key_id = (
            os.getenv("R2_ACCESS_KEY_ID")
            or os.getenv("CLOUDFLARE_R2_ACCESS_KEY_ID")
            or ""
        ).strip()
        self.secret_access_key = (
            os.getenv("R2_SECRET_ACCESS_KEY")
            or os.getenv("CLOUDFLARE_R2_SECRET_ACCESS_KEY")
            or ""
        ).strip()
        self.bucket_name = (
            os.getenv("R2_BUCKET_NAME")
            or os.getenv("CLOUDFLARE_R2_BUCKET_NAME")
            or "newspluk-media"
        ).strip()
        self.public_url = (
            os.getenv("R2_PUBLIC_URL")
            or os.getenv("CLOUDFLARE_R2_PUBLIC_URL")
            or ""
        ).rstrip("/")

        self._s3 = None

    def is_configured(self) -> bool:
        """Returns True if minimum required credentials for R2 are set."""
        return bool(self.account_id and self.access_key_id and self.secret_access_key and self.bucket_name)

    @property
    def client(self):
        """Lazy-instantiates the boto3 S3 client targeted at Cloudflare R2 endpoint."""
        if self._s3 is None and self.is_configured():
            try:
                import boto3
                from botocore.config import Config
                endpoint = f"https://{self.account_id}.r2.cloudflarestorage.com"
                self._s3 = boto3.client(
                    service_name="s3",
                    endpoint_url=endpoint,
                    aws_access_key_id=self.access_key_id,
                    aws_secret_access_key=self.secret_access_key,
                    config=Config(signature_version="s3v4", s3={"addressing_style": "virtual"})
                )
            except Exception as e:
                logging.error(f"[R2Storage] Failed to initialize S3 client: {e}")
                self._s3 = None
        return self._s3

    def upload_bytes(self, data: bytes, remote_key: str, content_type: str = None) -> str:
        """Uploads raw binary bytes to R2 bucket and returns the public CDN URL."""
        if not self.is_configured() or not self.client:
            return ""

        remote_key = remote_key.lstrip("/")
        extra_args = {"CacheControl": "public, max-age=31536000, immutable"}
        if content_type:
            extra_args["ContentType"] = content_type

        try:
            logging.info(f"[R2Storage] Uploading '{remote_key}' ({len(data)} bytes) to R2 bucket '{self.bucket_name}'...")
            self.client.put_object(
                Bucket=self.bucket_name,
                Key=remote_key,
                Body=data,
                **extra_args
            )
            logging.info(f"[R2Storage] Successfully uploaded '{remote_key}' to R2.")
            if self.public_url:
                return f"{self.public_url}/{remote_key}"
            return f"https://{self.bucket_name}.{self.account_id}.r2.cloudflarestorage.com/{remote_key}"
        except Exception as e:
            logging.warning(f"[R2Storage] Upload error for '{remote_key}': {e}")
            return ""

    def upload_file(self, local_path: str, remote_key: str, content_type: str = None) -> str:
        """Uploads a local file to R2 bucket."""
        if not os.path.exists(local_path):
            return ""
        try:
            with open(local_path, "rb") as f:
                data = f.read()
            return self.upload_bytes(data, remote_key, content_type=content_type)
        except Exception as e:
            logging.warning(f"[R2Storage] Failed reading file '{local_path}': {e}")
            return ""

    def delete_file(self, remote_key: str) -> bool:
        """Deletes an object from R2."""
        if not self.is_configured() or not self.client:
            return False
        try:
            self.client.delete_object(Bucket=self.bucket_name, Key=remote_key.lstrip("/"))
            logging.info(f"[R2Storage] Deleted '{remote_key}' from R2.")
            return True
        except Exception as e:
            logging.warning(f"[R2Storage] Delete error for '{remote_key}': {e}")
            return False


r2_service = R2StorageService()

"""R2 sync engine for persisting workspace files to Cloudflare R2."""

import fnmatch
import os
from pathlib import Path

import boto3
import modal
from botocore.exceptions import ClientError

# Default patterns to ignore during sync
DEFAULT_IGNORE_PATTERNS = [
    "node_modules/",
    "node_modules/**",
    "__pycache__/",
    "__pycache__/**",
    "*.pyc",
    ".git/",
    ".git/**",
    ".env",
    ".env.*",
    "*.log",
    ".DS_Store",
    ".venv/",
    ".venv/**",
    "dist/",
    "dist/**",
    ".next/",
    ".next/**",
]


class R2SyncError(Exception):
    """Raised when R2 sync operations fail."""

    pass


class R2Sync:
    """
    Sync files between local filesystem and Cloudflare R2 storage.

    R2 is S3-compatible, so we use boto3 with custom endpoint configuration.
    """

    def __init__(
        self,
        bucket_name: str | None = None,
        prefix: str = "",
        access_key_id: str | None = None,
        secret_access_key: str | None = None,
        endpoint_url: str | None = None,
    ):
        """
        Initialize R2Sync with bucket configuration.

        Args:
            bucket_name: R2 bucket name. Defaults to R2_BUCKET_NAME env var.
            prefix: Key prefix for all operations (e.g., "user123/project456/").
            access_key_id: R2 access key. Defaults to R2_ACCESS_KEY_ID env var.
            secret_access_key: R2 secret key. Defaults to R2_SECRET_ACCESS_KEY env var.
            endpoint_url: R2 endpoint URL. Defaults to R2_ENDPOINT_URL env var.
        """
        self.bucket_name = bucket_name or os.environ.get("R2_BUCKET_NAME")
        if not self.bucket_name:
            raise R2SyncError("Bucket name not provided and R2_BUCKET_NAME not set")

        self.prefix = prefix.rstrip("/") + "/" if prefix else ""

        # Get credentials from args or environment
        access_key = access_key_id or os.environ.get("R2_ACCESS_KEY_ID")
        secret_key = secret_access_key or os.environ.get("R2_SECRET_ACCESS_KEY")
        endpoint = endpoint_url or os.environ.get("R2_ENDPOINT_URL")

        if not all([access_key, secret_key, endpoint]):
            raise R2SyncError(
                "R2 credentials not fully configured. "
                "Set R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, and R2_ENDPOINT_URL"
            )

        self._client = boto3.client(
            "s3",
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            endpoint_url=endpoint,
        )

    def _should_ignore(self, path: str, ignore_patterns: list[str] | None) -> bool:
        """Check if a path should be ignored based on patterns."""
        patterns = ignore_patterns if ignore_patterns is not None else DEFAULT_IGNORE_PATTERNS

        for pattern in patterns:
            if fnmatch.fnmatch(path, pattern):
                return True
            # Also check if any parent directory matches
            parts = path.split("/")
            for i in range(len(parts)):
                partial = "/".join(parts[: i + 1])
                if fnmatch.fnmatch(partial, pattern.rstrip("/")):
                    return True
                if fnmatch.fnmatch(partial + "/", pattern):
                    return True

        return False

    def _get_local_files(
        self, local_dir: str, ignore_patterns: list[str] | None = None
    ) -> dict[str, Path]:
        """
        Get all files in local directory, excluding ignored patterns.

        Returns:
            Dict mapping relative path -> absolute Path object
        """
        local_path = Path(local_dir).resolve()
        files = {}

        if not local_path.exists():
            return files

        for file_path in local_path.rglob("*"):
            if not file_path.is_file():
                continue

            relative = str(file_path.relative_to(local_path))

            if self._should_ignore(relative, ignore_patterns):
                continue

            files[relative] = file_path

        return files

    def pull(self, local_dir: str, ignore_patterns: list[str] | None = None) -> int:
        """
        Download all files from R2 prefix to local directory.

        Args:
            local_dir: Local directory to download files to.
            ignore_patterns: List of glob patterns to ignore. Uses defaults if None.

        Returns:
            Number of files downloaded.

        Raises:
            R2SyncError: If download fails.
        """
        local_path = Path(local_dir).resolve()
        local_path.mkdir(parents=True, exist_ok=True)

        downloaded = 0
        try:
            remote_keys = self.list_remote()

            for key in remote_keys:
                # Remove prefix to get relative path
                relative_path = key[len(self.prefix) :] if self.prefix else key

                if self._should_ignore(relative_path, ignore_patterns):
                    continue

                local_file = local_path / relative_path
                self.download_file(key, str(local_file))
                downloaded += 1

        except ClientError as e:
            raise R2SyncError(f"Failed to pull from R2: {e}") from e

        return downloaded

    def push(self, local_dir: str, ignore_patterns: list[str] | None = None) -> int:
        """
        Upload all files from local directory to R2.

        Args:
            local_dir: Local directory to upload files from.
            ignore_patterns: List of glob patterns to ignore. Uses defaults if None.

        Returns:
            Number of files uploaded.

        Raises:
            R2SyncError: If upload fails.
        """
        files = self._get_local_files(local_dir, ignore_patterns)
        uploaded = 0

        try:
            for relative_path, file_path in files.items():
                remote_key = self.prefix + relative_path
                self.upload_file(str(file_path), remote_key)
                uploaded += 1

        except ClientError as e:
            raise R2SyncError(f"Failed to push to R2: {e}") from e

        return uploaded

    def upload_file(self, local_path: str, remote_key: str) -> None:
        """
        Upload a single file to R2.

        Args:
            local_path: Path to local file.
            remote_key: Full R2 key (including any prefix).

        Raises:
            R2SyncError: If upload fails.
        """
        try:
            self._client.upload_file(local_path, self.bucket_name, remote_key)
        except ClientError as e:
            raise R2SyncError(f"Failed to upload {local_path} to {remote_key}: {e}") from e

    def download_file(self, remote_key: str, local_path: str) -> None:
        """
        Download a single file from R2.

        Args:
            remote_key: Full R2 key (including any prefix).
            local_path: Path to save the file locally.

        Raises:
            R2SyncError: If download fails.
        """
        local_file = Path(local_path)
        local_file.parent.mkdir(parents=True, exist_ok=True)

        try:
            self._client.download_file(self.bucket_name, remote_key, str(local_file))
        except ClientError as e:
            raise R2SyncError(f"Failed to download {remote_key} to {local_path}: {e}") from e

    def list_remote(self, prefix: str = "") -> list[str]:
        """
        List all keys in R2 under the configured prefix.

        Args:
            prefix: Additional prefix to filter by (appended to instance prefix).

        Returns:
            List of full R2 keys.

        Raises:
            R2SyncError: If listing fails.
        """
        full_prefix = self.prefix + prefix
        keys = []

        try:
            paginator = self._client.get_paginator("list_objects_v2")
            pages = paginator.paginate(Bucket=self.bucket_name, Prefix=full_prefix)

            for page in pages:
                for obj in page.get("Contents", []):
                    keys.append(obj["Key"])

        except ClientError as e:
            raise R2SyncError(f"Failed to list R2 objects: {e}") from e

        return keys

    def delete_remote(self, remote_key: str) -> None:
        """
        Delete a file from R2.

        Args:
            remote_key: Full R2 key to delete.

        Raises:
            R2SyncError: If deletion fails.
        """
        try:
            self._client.delete_object(Bucket=self.bucket_name, Key=remote_key)
        except ClientError as e:
            raise R2SyncError(f"Failed to delete {remote_key}: {e}") from e

    def sync(
        self, local_dir: str, ignore_patterns: list[str] | None = None, delete: bool = False
    ) -> tuple[int, int, int]:
        """
        Bidirectional sync between local directory and R2.

        Files are compared by existence only (not content hash).
        Local files not in R2 are uploaded, R2 files not local are downloaded.

        Args:
            local_dir: Local directory to sync.
            ignore_patterns: List of glob patterns to ignore.
            delete: If True, delete remote files not present locally.

        Returns:
            Tuple of (uploaded_count, downloaded_count, deleted_count).
        """
        local_files = self._get_local_files(local_dir, ignore_patterns)
        remote_keys = set(self.list_remote())

        local_keys = {self.prefix + rel for rel in local_files.keys()}

        uploaded = 0
        downloaded = 0
        deleted = 0

        # Upload local files not in R2
        for relative_path, file_path in local_files.items():
            remote_key = self.prefix + relative_path
            if remote_key not in remote_keys:
                self.upload_file(str(file_path), remote_key)
                uploaded += 1

        # Download R2 files not locally
        local_path = Path(local_dir).resolve()
        for remote_key in remote_keys:
            if remote_key not in local_keys:
                relative = remote_key[len(self.prefix) :] if self.prefix else remote_key
                if not self._should_ignore(relative, ignore_patterns):
                    local_file = local_path / relative
                    self.download_file(remote_key, str(local_file))
                    downloaded += 1

        # Optionally delete remote files not present locally
        if delete:
            for remote_key in remote_keys:
                if remote_key not in local_keys:
                    self.delete_remote(remote_key)
                    deleted += 1

        return uploaded, downloaded, deleted


# Modal app for testing R2 connection
_test_app = modal.App("r2-connection-test")
_test_image = modal.Image.debian_slim(python_version="3.11").pip_install("boto3")


@_test_app.function(image=_test_image, secrets=[modal.Secret.from_name("r2-secret")])
def _test_r2_connection():
    """Remote function that tests R2 connection with secrets."""
    sync = R2Sync()
    keys = sync.list_remote()
    return len(keys), keys[:10] if keys else []


@_test_app.local_entrypoint()
def test_connection():
    """Test R2 connection by listing bucket contents."""
    try:
        count, sample_keys = _test_r2_connection.remote()
        print("Successfully connected to R2!")
        print(f"Found {count} objects in bucket")
        if sample_keys:
            print("First 10 keys:")
            for key in sample_keys:
                print(f"  - {key}")
    except R2SyncError as e:
        print(f"R2 connection failed: {e}")
        raise

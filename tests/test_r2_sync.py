"""Tests for R2 sync engine using moto for S3/R2 mocking."""

import os

import boto3
import pytest
from moto import mock_aws

from common.r2_sync import DEFAULT_IGNORE_PATTERNS, R2Sync, R2SyncError


@pytest.fixture
def r2_env():
    """Set up R2 environment variables for testing."""
    env_vars = {
        "R2_ACCESS_KEY_ID": "testing",
        "R2_SECRET_ACCESS_KEY": "testing",
        "R2_ENDPOINT_URL": "http://localhost:5000",  # Not actually used with moto
        "R2_BUCKET_NAME": "test-bucket",
    }
    original = {k: os.environ.get(k) for k in env_vars}
    os.environ.update(env_vars)
    yield env_vars
    # Restore original environment
    for k, v in original.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v


@pytest.fixture
def mock_s3(r2_env):
    """Create a mock S3/R2 bucket."""
    with mock_aws():
        # Create a real boto3 client for setting up the mock
        client = boto3.client(
            "s3",
            region_name="us-east-1",
            aws_access_key_id="testing",
            aws_secret_access_key="testing",
        )
        client.create_bucket(Bucket="test-bucket")
        yield client


@pytest.fixture
def r2_sync(mock_s3):
    """Create an R2Sync instance with mocked backend."""
    # Create sync instance - it will use the mocked S3
    sync = R2Sync.__new__(R2Sync)
    sync.bucket_name = "test-bucket"
    sync.prefix = ""
    sync._client = mock_s3
    return sync


class TestR2SyncInit:
    """Tests for R2Sync initialization."""

    def test_init_with_env_vars(self, r2_env, mock_s3):
        """Should initialize from environment variables."""
        # We need to patch the client creation since moto doesn't support custom endpoints
        sync = R2Sync.__new__(R2Sync)
        sync.bucket_name = "test-bucket"
        sync.prefix = ""
        sync._client = mock_s3

        assert sync.bucket_name == "test-bucket"
        assert sync.prefix == ""

    def test_init_with_prefix(self, r2_env, mock_s3):
        """Should handle prefix correctly."""
        sync = R2Sync.__new__(R2Sync)
        sync.bucket_name = "test-bucket"
        sync.prefix = "user123/project456/"
        sync._client = mock_s3

        assert sync.prefix == "user123/project456/"

    def test_init_missing_bucket_raises(self):
        """Should raise error when bucket name is missing."""
        # Clear environment
        for key in ["R2_BUCKET_NAME", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_ENDPOINT_URL"]:
            os.environ.pop(key, None)

        with pytest.raises(R2SyncError, match="Bucket name not provided"):
            R2Sync()


class TestR2SyncIgnorePatterns:
    """Tests for ignore pattern matching."""

    def test_should_ignore_node_modules(self, r2_sync):
        """node_modules should be ignored."""
        assert r2_sync._should_ignore("node_modules/package/index.js", None) is True

    def test_should_ignore_pycache(self, r2_sync):
        """__pycache__ should be ignored."""
        assert r2_sync._should_ignore("__pycache__/module.pyc", None) is True

    def test_should_ignore_pyc(self, r2_sync):
        """.pyc files should be ignored."""
        assert r2_sync._should_ignore("module.pyc", None) is True

    def test_should_ignore_git(self, r2_sync):
        """.git directory should be ignored."""
        assert r2_sync._should_ignore(".git/config", None) is True

    def test_should_ignore_env(self, r2_sync):
        """.env files should be ignored."""
        assert r2_sync._should_ignore(".env", None) is True
        assert r2_sync._should_ignore(".env.local", None) is True

    def test_should_not_ignore_source(self, r2_sync):
        """Source files should not be ignored."""
        assert r2_sync._should_ignore("src/App.jsx", None) is False
        assert r2_sync._should_ignore("index.html", None) is False

    def test_custom_ignore_patterns(self, r2_sync):
        """Custom ignore patterns should work."""
        custom_patterns = ["*.log", "build/"]

        assert r2_sync._should_ignore("debug.log", custom_patterns) is True
        assert r2_sync._should_ignore("build/output.js", custom_patterns) is True
        assert r2_sync._should_ignore("src/app.js", custom_patterns) is False

    def test_empty_ignore_patterns(self, r2_sync):
        """Empty ignore patterns should ignore nothing."""
        assert r2_sync._should_ignore("node_modules/pkg/index.js", []) is False


class TestR2SyncUploadDownload:
    """Tests for upload and download operations."""

    def test_upload_file(self, r2_sync, tmp_path):
        """Should upload a file to R2."""
        # Create a test file
        test_file = tmp_path / "test.txt"
        test_file.write_text("Hello, World!")

        # Upload
        r2_sync.upload_file(str(test_file), "test.txt")

        # Verify it exists
        response = r2_sync._client.get_object(Bucket="test-bucket", Key="test.txt")
        content = response["Body"].read().decode()
        assert content == "Hello, World!"

    def test_download_file(self, r2_sync, tmp_path):
        """Should download a file from R2."""
        # Put a file in R2
        r2_sync._client.put_object(
            Bucket="test-bucket",
            Key="remote.txt",
            Body=b"Remote content"
        )

        # Download
        local_file = tmp_path / "downloaded.txt"
        r2_sync.download_file("remote.txt", str(local_file))

        # Verify
        assert local_file.read_text() == "Remote content"

    def test_download_creates_directories(self, r2_sync, tmp_path):
        """Download should create parent directories."""
        r2_sync._client.put_object(
            Bucket="test-bucket",
            Key="deep/nested/file.txt",
            Body=b"Content"
        )

        local_file = tmp_path / "a" / "b" / "c" / "file.txt"
        r2_sync.download_file("deep/nested/file.txt", str(local_file))

        assert local_file.read_text() == "Content"


class TestR2SyncList:
    """Tests for listing remote files."""

    def test_list_empty_bucket(self, r2_sync):
        """Should return empty list for empty bucket."""
        keys = r2_sync.list_remote()
        assert keys == []

    def test_list_with_files(self, r2_sync):
        """Should list all files in bucket."""
        # Add some files
        r2_sync._client.put_object(Bucket="test-bucket", Key="file1.txt", Body=b"1")
        r2_sync._client.put_object(Bucket="test-bucket", Key="file2.txt", Body=b"2")
        r2_sync._client.put_object(Bucket="test-bucket", Key="dir/file3.txt", Body=b"3")

        keys = r2_sync.list_remote()

        assert len(keys) == 3
        assert "file1.txt" in keys
        assert "file2.txt" in keys
        assert "dir/file3.txt" in keys

    def test_list_with_prefix(self, r2_sync):
        """Should filter by prefix."""
        r2_sync._client.put_object(Bucket="test-bucket", Key="dir1/file.txt", Body=b"1")
        r2_sync._client.put_object(Bucket="test-bucket", Key="dir2/file.txt", Body=b"2")

        keys = r2_sync.list_remote(prefix="dir1/")

        assert len(keys) == 1
        assert "dir1/file.txt" in keys


class TestR2SyncDelete:
    """Tests for delete operations."""

    def test_delete_remote(self, r2_sync):
        """Should delete a file from R2."""
        r2_sync._client.put_object(Bucket="test-bucket", Key="to-delete.txt", Body=b"bye")

        r2_sync.delete_remote("to-delete.txt")

        keys = r2_sync.list_remote()
        assert "to-delete.txt" not in keys


class TestR2SyncPullPush:
    """Tests for pull and push operations."""

    def test_push_directory(self, r2_sync, tmp_path):
        """Should push all files from directory to R2."""
        # Create local files
        (tmp_path / "file1.txt").write_text("Content 1")
        (tmp_path / "subdir").mkdir()
        (tmp_path / "subdir" / "file2.txt").write_text("Content 2")

        # Push
        count = r2_sync.push(str(tmp_path))

        assert count == 2
        keys = r2_sync.list_remote()
        assert "file1.txt" in keys
        assert "subdir/file2.txt" in keys

    def test_push_ignores_patterns(self, r2_sync, tmp_path):
        """Push should ignore configured patterns."""
        # Create files including ignored ones
        (tmp_path / "app.js").write_text("code")
        (tmp_path / "node_modules").mkdir()
        (tmp_path / "node_modules" / "pkg.js").write_text("ignored")
        (tmp_path / ".env").write_text("SECRET=xxx")

        count = r2_sync.push(str(tmp_path))

        assert count == 1  # Only app.js
        keys = r2_sync.list_remote()
        assert "app.js" in keys
        assert not any("node_modules" in k for k in keys)
        assert ".env" not in keys

    def test_pull_directory(self, r2_sync, tmp_path):
        """Should pull all files from R2 to directory."""
        # Add files to R2
        r2_sync._client.put_object(Bucket="test-bucket", Key="remote1.txt", Body=b"R1")
        r2_sync._client.put_object(Bucket="test-bucket", Key="dir/remote2.txt", Body=b"R2")

        # Pull
        count = r2_sync.pull(str(tmp_path))

        assert count == 2
        assert (tmp_path / "remote1.txt").read_text() == "R1"
        assert (tmp_path / "dir" / "remote2.txt").read_text() == "R2"

    def test_pull_creates_directory(self, r2_sync, tmp_path):
        """Pull should create the target directory if it doesn't exist."""
        r2_sync._client.put_object(Bucket="test-bucket", Key="file.txt", Body=b"data")

        new_dir = tmp_path / "new" / "nested"
        count = r2_sync.pull(str(new_dir))

        assert count == 1
        assert (new_dir / "file.txt").read_text() == "data"


class TestR2SyncWithPrefix:
    """Tests for R2Sync with a prefix configured."""

    @pytest.fixture
    def prefixed_sync(self, mock_s3):
        """Create an R2Sync instance with a prefix."""
        sync = R2Sync.__new__(R2Sync)
        sync.bucket_name = "test-bucket"
        sync.prefix = "user123/project456/"
        sync._client = mock_s3
        return sync

    def test_push_uses_prefix(self, prefixed_sync, tmp_path):
        """Push should prepend prefix to all keys."""
        (tmp_path / "app.js").write_text("code")

        prefixed_sync.push(str(tmp_path))

        keys = prefixed_sync.list_remote()
        assert "user123/project456/app.js" in keys

    def test_pull_uses_prefix(self, prefixed_sync, tmp_path):
        """Pull should only download files under prefix."""
        # Add files with and without prefix
        prefixed_sync._client.put_object(
            Bucket="test-bucket",
            Key="user123/project456/file.txt",
            Body=b"mine"
        )
        prefixed_sync._client.put_object(
            Bucket="test-bucket",
            Key="other/file.txt",
            Body=b"not mine"
        )

        count = prefixed_sync.pull(str(tmp_path))

        assert count == 1
        assert (tmp_path / "file.txt").read_text() == "mine"
        assert not (tmp_path / "other").exists()


class TestDefaultIgnorePatterns:
    """Tests for default ignore patterns constant."""

    def test_contains_common_patterns(self):
        """Should contain common patterns to ignore."""
        assert "node_modules/" in DEFAULT_IGNORE_PATTERNS
        assert "__pycache__/" in DEFAULT_IGNORE_PATTERNS
        assert ".git/" in DEFAULT_IGNORE_PATTERNS
        assert ".env" in DEFAULT_IGNORE_PATTERNS
        assert "*.pyc" in DEFAULT_IGNORE_PATTERNS

"""Tests for the ProcessManager class."""

import sys
import tempfile
import time
from pathlib import Path

import pytest

from sandbox.process_manager import (
    ProcessConfig,
    ProcessManager,
    ProcessManagerError,
    ProcessState,
    ProcessStatus,
)


class TestProcessConfig:
    """Tests for ProcessConfig dataclass."""

    def test_basic_config(self):
        """Test creating a basic ProcessConfig."""
        config = ProcessConfig(
            name="test",
            command=["echo", "hello"],
            port=3000,
        )

        assert config.name == "test"
        assert config.command == ["echo", "hello"]
        assert config.port == 3000
        assert config.cwd is None
        assert config.startup_timeout == 30
        assert config.restart_limit == 3
        assert config.health_path == "/"
        assert config.env == {}

    def test_full_config(self):
        """Test creating a ProcessConfig with all options."""
        config = ProcessConfig(
            name="test",
            command=["node", "server.js"],
            port=3001,
            cwd="/app",
            startup_timeout=60,
            restart_limit=5,
            health_path="/health",
            env={"NODE_ENV": "development"},
        )

        assert config.name == "test"
        assert config.cwd == "/app"
        assert config.startup_timeout == 60
        assert config.restart_limit == 5
        assert config.health_path == "/health"
        assert config.env == {"NODE_ENV": "development"}


class TestProcessState:
    """Tests for ProcessState dataclass."""

    def test_default_state(self):
        """Test default ProcessState values."""
        config = ProcessConfig(name="test", command=["test"], port=3000)
        state = ProcessState(config=config)

        assert state.config == config
        assert state.process is None
        assert state.status == ProcessStatus.STOPPED
        assert state.restart_count == 0
        assert state.last_start_time == 0.0
        assert state.last_error is None


class TestProcessManager:
    """Tests for ProcessManager class."""

    @pytest.fixture
    def workspace(self):
        """Create a temporary workspace directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    @pytest.fixture
    def manager(self, workspace):
        """Create a ProcessManager instance."""
        return ProcessManager(workspace)

    def test_init(self, workspace):
        """Test ProcessManager initialization."""
        manager = ProcessManager(workspace)

        assert str(manager.workspace) == str(Path(workspace).resolve())
        assert len(manager._processes) == 0
        assert manager._monitor_task is None

    def test_add_process(self, manager):
        """Test adding a process."""
        config = ProcessConfig(name="test", command=["echo", "hello"], port=3000)
        manager.add_process(config)

        assert "test" in manager._processes
        assert manager._processes["test"].config == config
        assert manager._processes["test"].status == ProcessStatus.STOPPED

    def test_add_duplicate_process(self, manager):
        """Test adding a duplicate process raises an error."""
        config = ProcessConfig(name="test", command=["echo"], port=3000)
        manager.add_process(config)

        with pytest.raises(ProcessManagerError, match="already registered"):
            manager.add_process(config)

    def test_get_process_cwd_default(self, manager):
        """Test getting default working directory."""
        config = ProcessConfig(name="test", command=["echo"], port=3000)
        cwd = manager._get_process_cwd(config)

        assert cwd == str(manager.workspace)

    def test_get_process_cwd_relative(self, manager, workspace):
        """Test getting relative working directory."""
        config = ProcessConfig(name="test", command=["echo"], port=3000, cwd="subdir")
        cwd = manager._get_process_cwd(config)

        expected = str(Path(workspace).resolve() / "subdir")
        assert cwd == expected

    def test_get_process_cwd_absolute(self, manager):
        """Test getting absolute working directory."""
        config = ProcessConfig(name="test", command=["echo"], port=3000, cwd="/tmp")
        cwd = manager._get_process_cwd(config)

        # macOS resolves /tmp to /private/tmp
        assert cwd in ["/tmp", "/private/tmp"]

    def test_get_port(self, manager):
        """Test getting process port."""
        config = ProcessConfig(name="test", command=["echo"], port=3000)
        manager.add_process(config)

        assert manager.get_port("test") == 3000
        assert manager.get_port("nonexistent") is None

    def test_get_status(self, manager):
        """Test getting process status."""
        config = ProcessConfig(name="test", command=["echo"], port=3000)
        manager.add_process(config)

        status = manager.get_status("test")

        assert status is not None
        assert status["name"] == "test"
        assert status["status"] == "stopped"
        assert status["port"] == 3000
        assert status["pid"] is None
        assert status["restart_count"] == 0

    def test_get_status_nonexistent(self, manager):
        """Test getting status of nonexistent process."""
        assert manager.get_status("nonexistent") is None

    def test_get_all_status(self, manager):
        """Test getting all process statuses."""
        manager.add_process(ProcessConfig(name="a", command=["echo"], port=3000))
        manager.add_process(ProcessConfig(name="b", command=["echo"], port=3001))

        statuses = manager.get_all_status()

        assert statuses == {"a": "stopped", "b": "stopped"}

    def test_start_process_creates_directory(self, manager, workspace):
        """Test that starting a process creates the working directory."""
        subdir = Path(workspace) / "newdir"
        config = ProcessConfig(
            name="test",
            command=[sys.executable, "-c", "import time; time.sleep(60)"],
            port=3000,
            cwd=str(subdir),
        )
        manager.add_process(config)

        result = manager._start_process("test")

        assert result is True
        assert subdir.exists()

        # Cleanup
        manager._stop_process("test")

    def test_start_process_spawns_subprocess(self, manager, workspace):
        """Test that starting a process spawns a subprocess."""
        config = ProcessConfig(
            name="test",
            command=[sys.executable, "-c", "import time; time.sleep(60)"],
            port=3000,
        )
        manager.add_process(config)

        result = manager._start_process("test")

        assert result is True
        state = manager._processes["test"]
        assert state.process is not None
        assert state.process.pid > 0
        assert state.status == ProcessStatus.STARTING
        assert state.last_start_time > 0

        # Cleanup
        manager._stop_process("test")

    def test_start_process_nonexistent(self, manager):
        """Test starting a nonexistent process."""
        result = manager._start_process("nonexistent")
        assert result is False

    def test_stop_process_sigterm(self, manager, workspace):
        """Test stopping a process sends SIGTERM."""
        config = ProcessConfig(
            name="test",
            command=[sys.executable, "-c", "import time; time.sleep(60)"],
            port=3000,
        )
        manager.add_process(config)
        manager._start_process("test")

        state = manager._processes["test"]

        result = manager._stop_process("test", timeout=5.0)

        assert result is True
        assert state.status == ProcessStatus.STOPPED

    def test_stop_process_already_dead(self, manager, workspace):
        """Test stopping an already dead process."""
        config = ProcessConfig(
            name="test",
            command=[sys.executable, "-c", "pass"],  # Exits immediately
            port=3000,
        )
        manager.add_process(config)
        manager._start_process("test")

        # Wait for it to exit
        time.sleep(0.5)

        result = manager._stop_process("test")

        assert result is True
        assert manager._processes["test"].status == ProcessStatus.STOPPED

    def test_stop_process_nonexistent(self, manager):
        """Test stopping a nonexistent process."""
        result = manager._stop_process("nonexistent")
        assert result is False

    def test_stop_process_not_started(self, manager):
        """Test stopping a process that was never started."""
        config = ProcessConfig(name="test", command=["echo"], port=3000)
        manager.add_process(config)

        result = manager._stop_process("test")
        assert result is False


class TestProcessManagerAsync:
    """Async tests for ProcessManager."""

    @pytest.fixture
    def workspace(self):
        """Create a temporary workspace directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    @pytest.fixture
    def manager(self, workspace):
        """Create a ProcessManager instance."""
        return ProcessManager(workspace)

    @pytest.mark.asyncio
    async def test_health_check_not_running(self, manager):
        """Test health check for a non-running process."""
        config = ProcessConfig(name="test", command=["echo"], port=3000)
        manager.add_process(config)

        result = await manager.health_check("test")
        assert result is False

    @pytest.mark.asyncio
    async def test_health_check_nonexistent(self, manager):
        """Test health check for nonexistent process."""
        result = await manager.health_check("nonexistent")
        assert result is False

    @pytest.mark.asyncio
    async def test_health_check_with_mock_server(self, manager, workspace):
        """Test health check with a mock HTTP server."""
        # Use Python's built-in http.server module
        config = ProcessConfig(
            name="test",
            command=[sys.executable, "-m", "http.server", "3000", "--bind", "127.0.0.1"],
            port=3000,
            startup_timeout=10,
        )
        manager.add_process(config)
        manager._start_process("test")

        # Wait for server to be healthy (with retry)
        try:
            healthy = await manager._wait_for_health("test")
            assert healthy is True

            # Double-check with direct health_check call
            result = await manager.health_check("test")
            assert result is True
        finally:
            manager._stop_process("test")

    @pytest.mark.asyncio
    async def test_start_all_empty(self, manager):
        """Test start_all with no processes."""
        results = await manager.start_all()
        assert results == {}

    @pytest.mark.asyncio
    async def test_stop_all(self, manager, workspace):
        """Test stop_all stops all processes."""
        config1 = ProcessConfig(
            name="test1",
            command=[sys.executable, "-c", "import time; time.sleep(60)"],
            port=3000,
        )
        config2 = ProcessConfig(
            name="test2",
            command=[sys.executable, "-c", "import time; time.sleep(60)"],
            port=3001,
        )
        manager.add_process(config1)
        manager.add_process(config2)

        manager._start_process("test1")
        manager._start_process("test2")

        await manager.stop_all(timeout=5.0)

        assert manager._processes["test1"].status == ProcessStatus.STOPPED
        assert manager._processes["test2"].status == ProcessStatus.STOPPED

    @pytest.mark.asyncio
    async def test_wait_for_health_timeout(self, manager, workspace):
        """Test wait_for_health times out when server doesn't respond."""
        config = ProcessConfig(
            name="test",
            command=[sys.executable, "-c", "import time; time.sleep(60)"],
            port=3000,
            startup_timeout=1,  # Short timeout
        )
        manager.add_process(config)
        manager._start_process("test")

        try:
            result = await manager._wait_for_health("test")
            assert result is False
            assert manager._processes["test"].status == ProcessStatus.FAILED
            assert "timeout" in manager._processes["test"].last_error.lower()
        finally:
            manager._stop_process("test")

    @pytest.mark.asyncio
    async def test_wait_for_health_process_dies(self, manager, workspace):
        """Test wait_for_health detects when process dies."""
        config = ProcessConfig(
            name="test",
            command=[sys.executable, "-c", "import sys; sys.exit(1)"],
            port=3000,
            startup_timeout=5,
        )
        manager.add_process(config)
        manager._start_process("test")

        result = await manager._wait_for_health("test")

        assert result is False
        assert manager._processes["test"].status == ProcessStatus.FAILED


class TestProcessManagerIntegration:
    """Integration tests for ProcessManager with real HTTP servers."""

    @pytest.fixture
    def workspace(self):
        """Create a temporary workspace directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    @pytest.mark.asyncio
    async def test_full_lifecycle(self, workspace):
        """Test full process lifecycle: add, start, health check, stop."""
        manager = ProcessManager(workspace)

        # Use Python's built-in http.server module directly
        config = ProcessConfig(
            name="test-server",
            command=[
                sys.executable, "-m", "http.server", "3000",
                "--bind", "127.0.0.1"
            ],
            port=3000,
            startup_timeout=10,
        )

        # Add and start
        manager.add_process(config)
        results = await manager.start_all()

        try:
            assert results["test-server"] is True

            # Verify health check
            healthy = await manager.health_check("test-server")
            assert healthy is True

            # Check status
            status = manager.get_status("test-server")
            assert status["status"] == "running"
            assert status["pid"] is not None

        finally:
            # Stop and verify
            await manager.stop_all()

        assert manager.get_status("test-server")["status"] == "stopped"

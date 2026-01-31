"""Process manager for spawning and monitoring dev server subprocesses."""

import asyncio
import logging
import signal
import subprocess
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

import aiohttp

logger = logging.getLogger(__name__)


class ProcessStatus(Enum):
    """Status of a managed process."""

    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    FAILED = "failed"


@dataclass
class ProcessConfig:
    """Configuration for a managed subprocess."""

    name: str
    command: list[str]
    port: int
    cwd: str | None = None
    startup_timeout: int = 30
    restart_limit: int = 3
    health_path: str = "/"
    env: dict[str, str] = field(default_factory=dict)


@dataclass
class ProcessState:
    """Runtime state of a managed process."""

    config: ProcessConfig
    process: subprocess.Popen | None = None
    status: ProcessStatus = ProcessStatus.STOPPED
    restart_count: int = 0
    last_start_time: float = 0.0
    last_error: str | None = None


class ProcessManagerError(Exception):
    """Raised when process management operations fail."""

    pass


class ProcessManager:
    """
    Manages multiple dev server subprocesses with health monitoring and auto-restart.

    Each process is identified by name and configured with a command, port, and
    optional working directory. The manager handles:
    - Starting all processes
    - Health checking via HTTP polling
    - Auto-restarting failed processes with backoff
    - Graceful shutdown (SIGTERM → wait → SIGKILL)
    """

    def __init__(self, workspace: str):
        """
        Initialize the ProcessManager.

        Args:
            workspace: Base workspace directory for process working directories.
        """
        self.workspace = Path(workspace).resolve()
        self._processes: dict[str, ProcessState] = {}
        self._shutdown_event = asyncio.Event()
        self._monitor_task: asyncio.Task | None = None

    def add_process(self, config: ProcessConfig) -> None:
        """
        Add a process configuration to be managed.

        Args:
            config: ProcessConfig defining the process to manage.

        Raises:
            ProcessManagerError: If a process with the same name already exists.
        """
        if config.name in self._processes:
            raise ProcessManagerError(f"Process '{config.name}' already registered")

        self._processes[config.name] = ProcessState(config=config)
        logger.info(f"Registered process '{config.name}' on port {config.port}")

    def _get_process_cwd(self, config: ProcessConfig) -> str:
        """Get the working directory for a process."""
        if config.cwd:
            cwd = Path(config.cwd)
            if not cwd.is_absolute():
                cwd = self.workspace / cwd
        else:
            cwd = self.workspace
        return str(cwd.resolve())

    def _start_process(self, name: str) -> bool:
        """
        Start a single process.

        Args:
            name: Name of the process to start.

        Returns:
            True if the process was started, False otherwise.
        """
        state = self._processes.get(name)
        if not state:
            logger.error(f"Process '{name}' not found")
            return False

        if state.status == ProcessStatus.RUNNING and state.process:
            if state.process.poll() is None:
                logger.debug(f"Process '{name}' is already running")
                return True

        config = state.config
        cwd = self._get_process_cwd(config)

        # Ensure working directory exists
        cwd_path = Path(cwd)
        cwd_path.mkdir(parents=True, exist_ok=True)

        # Merge environment variables
        env = dict(subprocess.os.environ)
        env.update(config.env)

        try:
            state.status = ProcessStatus.STARTING
            state.process = subprocess.Popen(
                config.command,
                cwd=cwd,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                start_new_session=True,  # Create new process group for cleanup
            )
            state.last_start_time = time.time()
            logger.info(
                f"Started process '{name}' (PID: {state.process.pid}) "
                f"with command: {' '.join(config.command)}"
            )
            return True

        except Exception as e:
            state.status = ProcessStatus.FAILED
            state.last_error = str(e)
            logger.error(f"Failed to start process '{name}': {e}")
            return False

    async def _wait_for_health(self, name: str) -> bool:
        """
        Wait for a process to become healthy.

        Args:
            name: Name of the process to check.

        Returns:
            True if the process became healthy, False if timeout.
        """
        state = self._processes.get(name)
        if not state:
            return False

        config = state.config
        url = f"http://127.0.0.1:{config.port}{config.health_path}"
        deadline = time.time() + config.startup_timeout

        async with aiohttp.ClientSession() as session:
            while time.time() < deadline:
                # Check if process died
                if state.process and state.process.poll() is not None:
                    exit_code = state.process.returncode
                    state.status = ProcessStatus.FAILED
                    state.last_error = f"Process exited with code {exit_code}"
                    logger.error(f"Process '{name}' died during startup: {state.last_error}")
                    return False

                try:
                    async with session.get(url, timeout=aiohttp.ClientTimeout(total=2)) as resp:
                        if resp.status < 500:
                            state.status = ProcessStatus.RUNNING
                            logger.info(f"Process '{name}' is healthy on port {config.port}")
                            return True
                except (TimeoutError, aiohttp.ClientError):
                    pass

                await asyncio.sleep(0.5)

        state.status = ProcessStatus.FAILED
        state.last_error = f"Startup timeout after {config.startup_timeout}s"
        logger.error(f"Process '{name}' failed health check: {state.last_error}")
        return False

    async def health_check(self, name: str) -> bool:
        """
        Check if a process is healthy.

        Args:
            name: Name of the process to check.

        Returns:
            True if the process is healthy, False otherwise.
        """
        state = self._processes.get(name)
        if not state:
            return False

        # Check if process is running
        if not state.process or state.process.poll() is not None:
            return False

        config = state.config
        url = f"http://127.0.0.1:{config.port}{config.health_path}"

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                    return resp.status < 500
        except (TimeoutError, aiohttp.ClientError):
            return False

    async def start_all(self) -> dict[str, bool]:
        """
        Start all registered processes and wait for them to be healthy.

        Returns:
            Dict mapping process name to success status.
        """
        results = {}

        for name in self._processes:
            if self._start_process(name):
                healthy = await self._wait_for_health(name)
                results[name] = healthy
            else:
                results[name] = False

        # Start the background monitor if any process started successfully
        if any(results.values()) and not self._monitor_task:
            self._shutdown_event.clear()
            self._monitor_task = asyncio.create_task(self._monitor_loop())

        return results

    async def _monitor_loop(self) -> None:
        """Background task that monitors and restarts failed processes."""
        while not self._shutdown_event.is_set():
            for name, state in self._processes.items():
                if state.status == ProcessStatus.STOPPED:
                    continue

                # Check if process died
                if state.process and state.process.poll() is not None:
                    exit_code = state.process.returncode
                    logger.warning(f"Process '{name}' exited with code {exit_code}")

                    if state.restart_count < state.config.restart_limit:
                        state.restart_count += 1
                        backoff = min(2**state.restart_count, 30)
                        logger.info(
                            f"Restarting '{name}' (attempt {state.restart_count}/"
                            f"{state.config.restart_limit}) after {backoff}s backoff"
                        )
                        await asyncio.sleep(backoff)

                        if self._shutdown_event.is_set():
                            break

                        if self._start_process(name):
                            await self._wait_for_health(name)
                            if state.status == ProcessStatus.RUNNING:
                                state.restart_count = 0  # Reset on successful restart
                    else:
                        state.status = ProcessStatus.FAILED
                        state.last_error = (
                            f"Exceeded restart limit ({state.config.restart_limit})"
                        )
                        logger.error(f"Process '{name}' exceeded restart limit")

            try:
                await asyncio.wait_for(self._shutdown_event.wait(), timeout=5.0)
                break  # Shutdown requested
            except TimeoutError:
                pass  # Continue monitoring

    def _stop_process(self, name: str, timeout: float = 5.0) -> bool:
        """
        Stop a single process gracefully.

        Args:
            name: Name of the process to stop.
            timeout: Seconds to wait for graceful shutdown before SIGKILL.

        Returns:
            True if the process was stopped, False if it wasn't running.
        """
        state = self._processes.get(name)
        if not state or not state.process:
            return False

        if state.process.poll() is not None:
            # Already dead
            state.status = ProcessStatus.STOPPED
            return True

        pid = state.process.pid
        logger.info(f"Stopping process '{name}' (PID: {pid})")

        try:
            # Send SIGTERM to process group
            pgid = subprocess.os.getpgid(pid)
            subprocess.os.killpg(pgid, signal.SIGTERM)
        except (ProcessLookupError, PermissionError):
            # Process already gone or can't signal it
            state.status = ProcessStatus.STOPPED
            return True

        # Wait for graceful shutdown
        deadline = time.time() + timeout
        while time.time() < deadline:
            if state.process.poll() is not None:
                state.status = ProcessStatus.STOPPED
                logger.info(f"Process '{name}' stopped gracefully")
                return True
            time.sleep(0.1)

        # Force kill if still running
        logger.warning(f"Process '{name}' didn't stop gracefully, sending SIGKILL")
        try:
            pgid = subprocess.os.getpgid(pid)
            subprocess.os.killpg(pgid, signal.SIGKILL)
            state.process.wait(timeout=2)
        except (ProcessLookupError, PermissionError, subprocess.TimeoutExpired):
            pass

        state.status = ProcessStatus.STOPPED
        return True

    async def stop_all(self, timeout: float = 10.0) -> None:
        """
        Stop all managed processes gracefully.

        Args:
            timeout: Total seconds to wait for all processes to stop.
        """
        # Signal monitor to stop
        self._shutdown_event.set()

        if self._monitor_task:
            try:
                await asyncio.wait_for(self._monitor_task, timeout=2.0)
            except TimeoutError:
                self._monitor_task.cancel()
                try:
                    await self._monitor_task
                except asyncio.CancelledError:
                    pass
            self._monitor_task = None

        # Stop all processes
        per_process_timeout = timeout / max(len(self._processes), 1)
        for name in self._processes:
            self._stop_process(name, timeout=per_process_timeout)

        logger.info("All processes stopped")

    def get_status(self, name: str) -> dict | None:
        """
        Get the status of a specific process.

        Args:
            name: Name of the process.

        Returns:
            Dict with process status info, or None if not found.
        """
        state = self._processes.get(name)
        if not state:
            return None

        return {
            "name": name,
            "status": state.status.value,
            "port": state.config.port,
            "pid": state.process.pid if state.process else None,
            "restart_count": state.restart_count,
            "last_error": state.last_error,
        }

    def get_all_status(self) -> dict[str, str]:
        """
        Get the status of all managed processes.

        Returns:
            Dict mapping process name to status string.
        """
        return {name: state.status.value for name, state in self._processes.items()}

    def get_port(self, name: str) -> int | None:
        """
        Get the port number for a process.

        Args:
            name: Name of the process.

        Returns:
            Port number, or None if process not found.
        """
        state = self._processes.get(name)
        return state.config.port if state else None

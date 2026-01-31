"""ProjectSandbox Modal class for running multi-process dev environments."""

import logging
from pathlib import Path

import modal

# Import from local packages
from sandbox.image import sandbox_image

logger = logging.getLogger(__name__)

# Extend sandbox image to include local Python packages
sandbox_image_with_packages = sandbox_image.add_local_python_source("common", "gateway", "sandbox")

# Import from local packages (after image is set up, these are runtime imports)
from common.r2_sync import R2Sync
from gateway.router import MODULE_PORTS, create_gateway_app
from sandbox.process_manager import ProcessConfig, ProcessManager

# Modal app definition
app = modal.App("devlabo-sandbox")

# Workspace paths inside the container
WORKSPACE_ROOT = "/root/workspace"
WORKSPACE_DIRS = ["prototype", "frontend", "dbml", "test-case"]

# Default user/project for the ASGI web endpoint
DEFAULT_USER_ID = "default"
DEFAULT_PROJECT_ID = "default"


def get_default_process_configs() -> list[ProcessConfig]:
    """
    Get default ProcessConfig for each dev server.

    For now, we use Python's http.server for all modules since Vite requires
    package.json setup. In the future, when projects are properly scaffolded,
    we can switch to Vite for prototype and frontend.

    Returns:
        List of ProcessConfig for prototype, frontend, dbml, and test-case servers.
    """
    return [
        # Use Python http.server for all modules (fast startup, no deps)
        ProcessConfig(
            name="prototype",
            command=["python", "-m", "http.server", "3001", "--bind", "0.0.0.0"],
            port=MODULE_PORTS["prototype"],
            cwd="prototype",
            startup_timeout=10,
            health_path="/",
        ),
        ProcessConfig(
            name="frontend",
            command=["python", "-m", "http.server", "3002", "--bind", "0.0.0.0"],
            port=MODULE_PORTS["frontend"],
            cwd="frontend",
            startup_timeout=10,
            health_path="/",
        ),
        ProcessConfig(
            name="dbml",
            command=["python", "-m", "http.server", "3003", "--bind", "0.0.0.0"],
            port=MODULE_PORTS["dbml"],
            cwd="dbml",
            startup_timeout=10,
            health_path="/",
        ),
        ProcessConfig(
            name="tests",
            command=["python", "-m", "http.server", "3004", "--bind", "0.0.0.0"],
            port=MODULE_PORTS["tests"],
            cwd="test-case",
            startup_timeout=10,
            health_path="/",
        ),
    ]


@app.cls(
    image=sandbox_image_with_packages,
    secrets=[modal.Secret.from_name("r2-secret")],
    timeout=3600,  # 1 hour max lifetime
    scaledown_window=300,  # 5 min idle timeout (renamed from container_idle_timeout)
)
@modal.concurrent(max_inputs=100)
class ProjectSandbox:
    """
    Modal class that runs a multi-process sandbox for a user's project.

    Combines:
    - R2 sync for persistent storage
    - ProcessManager for 4 dev servers
    - FastAPI gateway for HTTP/WebSocket routing
    """

    # Use modal.parameter() for parameterization (Modal 1.0 pattern)
    user_id: str = modal.parameter(default=DEFAULT_USER_ID)
    project_id: str = modal.parameter(default=DEFAULT_PROJECT_ID)

    @modal.enter()
    def startup(self):
        """
        Container startup lifecycle hook.

        1. Creates workspace directories
        2. Pulls files from R2
        3. Sets up scaffold files if directories are empty
        4. Starts all dev server processes
        """
        self.workspace = WORKSPACE_ROOT
        self.r2_prefix = f"{self.user_id}/{self.project_id}/"
        self._process_manager: ProcessManager | None = None
        self._r2_sync: R2Sync | None = None

        logger.info(f"Starting sandbox for {self.user_id}/{self.project_id}")

        # 1. Create workspace directories
        self._create_workspace_dirs()

        # 2. Initialize R2 sync and pull files
        self._setup_r2_sync()
        self._pull_from_r2()

        # 3. Set up scaffold files for empty directories
        self._setup_scaffolds()

        # 4. Initialize and start ProcessManager
        self._start_processes()

        # 5. Create gateway app
        self._gateway_app = create_gateway_app(
            process_manager=self._process_manager,
            client_timeout=30.0,
        )

        logger.info("Sandbox startup complete")

    @modal.exit()
    def shutdown(self):
        """
        Container shutdown lifecycle hook.

        1. Stops all dev server processes
        2. Pushes files to R2
        """
        logger.info(f"Shutting down sandbox for {self.user_id}/{self.project_id}")

        # 1. Stop all processes
        if self._process_manager:
            import asyncio

            loop = asyncio.new_event_loop()
            try:
                loop.run_until_complete(self._process_manager.stop_all(timeout=10.0))
            finally:
                loop.close()

        # 2. Push files to R2
        self._push_to_r2()

        logger.info("Sandbox shutdown complete")

    @modal.asgi_app()
    def gateway(self):
        """Expose the FastAPI gateway as an ASGI app."""
        return self._gateway_app

    def _create_workspace_dirs(self) -> None:
        """Create workspace directories."""
        workspace_path = Path(self.workspace)
        workspace_path.mkdir(parents=True, exist_ok=True)

        for dirname in WORKSPACE_DIRS:
            dir_path = workspace_path / dirname
            dir_path.mkdir(parents=True, exist_ok=True)
            logger.debug(f"Created directory: {dir_path}")

    def _setup_r2_sync(self) -> None:
        """Initialize R2 sync client."""
        try:
            self._r2_sync = R2Sync(prefix=self.r2_prefix)
            logger.info(f"R2 sync initialized with prefix: {self.r2_prefix}")
        except Exception as e:
            logger.warning(f"R2 sync initialization failed: {e}")
            self._r2_sync = None

    def _pull_from_r2(self) -> None:
        """Pull files from R2 to workspace."""
        if not self._r2_sync:
            logger.warning("Skipping R2 pull - sync not initialized")
            return

        try:
            count = self._r2_sync.pull(self.workspace)
            logger.info(f"Pulled {count} files from R2")
        except Exception as e:
            logger.warning(f"R2 pull failed: {e}")

    def _push_to_r2(self) -> None:
        """Push files from workspace to R2."""
        if not self._r2_sync:
            logger.warning("Skipping R2 push - sync not initialized")
            return

        try:
            count = self._r2_sync.push(self.workspace)
            logger.info(f"Pushed {count} files to R2")
        except Exception as e:
            logger.warning(f"R2 push failed: {e}")

    def _setup_scaffolds(self) -> None:
        """Set up scaffold files for empty directories."""
        workspace_path = Path(self.workspace)

        # Prototype scaffold: basic index.html
        prototype_dir = workspace_path / "prototype"
        index_html = prototype_dir / "index.html"
        if not index_html.exists():
            index_html.write_text(
                """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>DevLabo Prototype</title>
</head>
<body>
    <h1>Hello World</h1>
    <p>Edit this file to start building your prototype.</p>
</body>
</html>
"""
            )
            logger.debug("Created prototype scaffold: index.html")

        # Frontend scaffold: basic Vite config and index.html
        frontend_dir = workspace_path / "frontend"
        frontend_index = frontend_dir / "index.html"
        if not frontend_index.exists():
            frontend_index.write_text(
                """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>DevLabo Frontend</title>
</head>
<body>
    <div id="app"></div>
    <script type="module" src="src/main.js"></script>
</body>
</html>
"""
            )

            # Create src directory and main.js
            src_dir = frontend_dir / "src"
            src_dir.mkdir(exist_ok=True)
            main_js = src_dir / "main.js"
            if not main_js.exists():
                main_js.write_text(
                    """// Frontend entry point
document.getElementById('app').innerHTML = '<h1>Frontend Ready</h1>';
"""
                )
            logger.debug("Created frontend scaffold")

        # DBML scaffold: basic README
        dbml_dir = workspace_path / "dbml"
        dbml_readme = dbml_dir / "index.html"
        if not dbml_readme.exists():
            dbml_readme.write_text(
                """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>DBML Schema</title>
</head>
<body>
    <h1>Database Schema</h1>
    <p>DBML schema visualization will appear here.</p>
</body>
</html>
"""
            )
            logger.debug("Created DBML scaffold")

        # Test-case scaffold: basic test file
        test_dir = workspace_path / "test-case"
        test_index = test_dir / "index.html"
        if not test_index.exists():
            test_index.write_text(
                """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Test Runner</title>
</head>
<body>
    <h1>Test Runner</h1>
    <p>Vitest UI will run here.</p>
</body>
</html>
"""
            )
            logger.debug("Created test-case scaffold")

    def _start_processes(self) -> None:
        """Initialize and start all dev server processes."""
        self._process_manager = ProcessManager(self.workspace)

        # Register all process configs
        for config in get_default_process_configs():
            self._process_manager.add_process(config)

        # Start all processes (async)
        import asyncio

        loop = asyncio.new_event_loop()
        try:
            results = loop.run_until_complete(self._process_manager.start_all())
            for name, success in results.items():
                status = "started" if success else "failed"
                logger.info(f"Process '{name}': {status}")
        finally:
            loop.close()

    @modal.method()
    def get_status(self) -> dict:
        """
        Get the status of all processes and R2 sync.

        Returns:
            Dict with process statuses and R2 sync status.
        """
        result = {
            "user_id": self.user_id,
            "project_id": self.project_id,
            "workspace": self.workspace,
            "r2_prefix": self.r2_prefix,
            "r2_connected": self._r2_sync is not None,
        }

        if self._process_manager:
            result["processes"] = {}
            for name in ["prototype", "frontend", "dbml", "tests"]:
                status = self._process_manager.get_status(name)
                if status:
                    result["processes"][name] = status

        return result

    @modal.method()
    def sync_to_r2(self) -> int:
        """
        Manually trigger sync to R2.

        Returns:
            Number of files pushed to R2.
        """
        if not self._r2_sync:
            return 0

        try:
            return self._r2_sync.push(self.workspace)
        except Exception as e:
            logger.error(f"Manual R2 sync failed: {e}")
            return 0

    @modal.method()
    def restart_process(self, name: str) -> bool:
        """
        Restart a specific process.

        Args:
            name: Process name to restart.

        Returns:
            True if restart was successful.
        """
        if not self._process_manager:
            return False

        import asyncio

        loop = asyncio.new_event_loop()
        try:
            # Stop the process
            self._process_manager._stop_process(name)

            # Start it again
            if self._process_manager._start_process(name):
                return loop.run_until_complete(
                    self._process_manager._wait_for_health(name)
                )
            return False
        finally:
            loop.close()


# Standalone test entrypoint
@app.local_entrypoint()
def test_sandbox():
    """Test the sandbox locally."""
    print("Creating ProjectSandbox instance...")
    sandbox = ProjectSandbox()

    print("\nGetting status...")
    status = sandbox.get_status.remote()
    print(f"Status: {status}")

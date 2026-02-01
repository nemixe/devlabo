"""LangChain-compatible tools for file operations.

Supports two modes:
1. Direct mode: Tools use direct filesystem access (when running inside container)
2. RPC mode: Tools use Sandbox RPC calls (when running outside container)
"""

import logging
import shutil
import subprocess
from pathlib import Path
from typing import Any

from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

from security.utils import get_scoped_path

logger = logging.getLogger(__name__)

# Scopes the agent is allowed to write to
WRITABLE_SCOPES: frozenset[str] = frozenset({"frontend", "dbml", "test-case"})


class ReadFileInput(BaseModel):
    """Input schema for ReadFileTool."""

    scope: str = Field(
        description="The scope directory to read from (prototype, frontend, dbml, test-case)"
    )
    path: str = Field(description="The relative path to the file within the scope")


class ReadFileTool(BaseTool):
    """Tool for reading files from the project workspace."""

    name: str = "read_file"
    description: str = (
        "Read a file from the project. Use scope='prototype' to read source files, "
        "'frontend' for generated code, 'dbml' for database schemas, 'test-case' for tests."
    )
    args_schema: type[BaseModel] = ReadFileInput

    # One of these must be set
    workspace: str | None = None  # For direct mode
    sandbox: Any = None  # For RPC mode

    def _run(self, scope: str, path: str) -> str:
        """Read file via direct access or Sandbox RPC."""
        if self.workspace:
            # Direct mode - read from filesystem
            try:
                validated_path = get_scoped_path(self.workspace, scope, path)
                return Path(validated_path).read_text()
            except FileNotFoundError:
                return f"Error: File '{path}' not found in scope '{scope}'"
            except Exception as e:
                return f"Error reading file: {e}"
        elif self.sandbox:
            # RPC mode - call sandbox
            try:
                return self.sandbox.read_file.remote(scope=scope, relative_path=path)
            except FileNotFoundError:
                return f"Error: File '{path}' not found in scope '{scope}'"
            except Exception as e:
                return f"Error reading file: {e}"
        else:
            return "Error: Tool not configured (no workspace or sandbox)"


class WriteFileInput(BaseModel):
    """Input schema for WriteFileTool."""

    scope: str = Field(
        description="The scope directory to write to (frontend, dbml, test-case). "
        "Note: 'prototype' is read-only for the agent."
    )
    path: str = Field(description="The relative path to the file within the scope")
    content: str = Field(description="The content to write to the file")


class WriteFileTool(BaseTool):
    """Tool for writing files to the project workspace."""

    name: str = "write_file"
    description: str = (
        "Write a file to the project. Use scope='frontend' for React/production code, "
        "'dbml' for database schemas, 'test-case' for tests. "
        "Note: 'prototype' is read-only and cannot be written to by the agent."
    )
    args_schema: type[BaseModel] = WriteFileInput

    # One of these must be set
    workspace: str | None = None  # For direct mode
    sandbox: Any = None  # For RPC mode

    def _run(self, scope: str, path: str, content: str) -> str:
        """Write file via direct access or Sandbox RPC."""
        # Prevent writing to prototype (read-only source of truth)
        if scope not in WRITABLE_SCOPES:
            return f"Error: Cannot write to scope '{scope}'. Writable scopes: {', '.join(sorted(WRITABLE_SCOPES))}"

        if self.workspace:
            # Direct mode - write to filesystem
            try:
                validated_path = get_scoped_path(self.workspace, scope, path)
                path_obj = Path(validated_path)
                path_obj.parent.mkdir(parents=True, exist_ok=True)
                path_obj.write_text(content)
                return f"Successfully wrote '{path}' to scope '{scope}'"
            except Exception as e:
                return f"Error writing file: {e}"
        elif self.sandbox:
            # RPC mode - call sandbox
            try:
                self.sandbox.write_file.remote(scope=scope, relative_path=path, content=content)
                return f"Successfully wrote '{path}' to scope '{scope}'"
            except Exception as e:
                return f"Error writing file: {e}"
        else:
            return "Error: Tool not configured (no workspace or sandbox)"


class ListFilesInput(BaseModel):
    """Input schema for ListFilesTool."""

    scope: str = Field(
        description="The scope directory to list (prototype, frontend, dbml, test-case)"
    )


class ListFilesTool(BaseTool):
    """Tool for listing files in a project scope."""

    name: str = "list_files"
    description: str = (
        "List all files in a scope directory. "
        "Available scopes: prototype (source), frontend (generated), dbml (schemas), test-case (tests)."
    )
    args_schema: type[BaseModel] = ListFilesInput

    # One of these must be set
    workspace: str | None = None  # For direct mode
    sandbox: Any = None  # For RPC mode

    def _run(self, scope: str) -> str:
        """List files via direct access or Sandbox RPC."""
        if self.workspace:
            # Direct mode - list from filesystem
            try:
                scope_path = Path(self.workspace) / scope
                if not scope_path.exists():
                    return f"No files found in scope '{scope}'"
                files = [str(f.relative_to(scope_path)) for f in scope_path.rglob("*") if f.is_file()]
                if not files:
                    return f"No files found in scope '{scope}'"
                return f"Files in '{scope}':\n" + "\n".join(f"  - {f}" for f in sorted(files))
            except Exception as e:
                return f"Error listing files: {e}"
        elif self.sandbox:
            # RPC mode - call sandbox
            try:
                files = self.sandbox.list_files.remote(scope=scope)
                if not files:
                    return f"No files found in scope '{scope}'"
                return f"Files in '{scope}':\n" + "\n".join(f"  - {f}" for f in sorted(files))
            except Exception as e:
                return f"Error listing files: {e}"
        else:
            return "Error: Tool not configured (no workspace or sandbox)"


class DeleteFileInput(BaseModel):
    """Input schema for DeleteFileTool."""

    scope: str = Field(
        description="The scope directory to delete from (frontend, dbml, test-case). "
        "Note: 'prototype' is read-only."
    )
    path: str = Field(description="The relative path to the file to delete")


class DeleteFileTool(BaseTool):
    """Tool for deleting files from the project workspace."""

    name: str = "delete_file"
    description: str = (
        "Delete a file from the project. Use scope='frontend' for generated code, "
        "'dbml' for database schemas, 'test-case' for tests. "
        "Note: 'prototype' is read-only and files cannot be deleted from it."
    )
    args_schema: type[BaseModel] = DeleteFileInput

    # One of these must be set
    workspace: str | None = None  # For direct mode
    sandbox: Any = None  # For RPC mode

    def _run(self, scope: str, path: str) -> str:
        """Delete file via direct access or Sandbox RPC."""
        if scope not in WRITABLE_SCOPES:
            return f"Error: Cannot delete from scope '{scope}'. Writable scopes: {', '.join(sorted(WRITABLE_SCOPES))}"

        if self.workspace:
            # Direct mode - delete from filesystem
            try:
                validated_path = get_scoped_path(self.workspace, scope, path)
                path_obj = Path(validated_path)
                if not path_obj.exists():
                    return f"Error: File '{path}' not found in scope '{scope}'"
                path_obj.unlink()
                return f"Successfully deleted '{path}' from scope '{scope}'"
            except Exception as e:
                return f"Error deleting file: {e}"
        elif self.sandbox:
            # RPC mode - call sandbox
            try:
                self.sandbox.delete_file.remote(scope=scope, relative_path=path)
                return f"Successfully deleted '{path}' from scope '{scope}'"
            except FileNotFoundError:
                return f"Error: File '{path}' not found in scope '{scope}'"
            except Exception as e:
                return f"Error deleting file: {e}"
        else:
            return "Error: Tool not configured (no workspace or sandbox)"


class DeleteFilesInput(BaseModel):
    """Input schema for DeleteFilesTool."""

    scope: str = Field(
        description="The scope directory to delete from (frontend, dbml, test-case). "
        "Note: 'prototype' is read-only."
    )
    paths: list[str] = Field(description="List of relative paths to delete")


class DeleteFilesTool(BaseTool):
    """Tool for bulk deleting files from the project workspace."""

    name: str = "delete_files"
    description: str = (
        "Bulk delete multiple files from the project. Use this instead of calling "
        "delete_file multiple times. Returns detailed success/failure info. "
        "Note: 'prototype' is read-only."
    )
    args_schema: type[BaseModel] = DeleteFilesInput

    # One of these must be set
    workspace: str | None = None  # For direct mode
    sandbox: Any = None  # For RPC mode

    def _run(self, scope: str, paths: list[str]) -> str:
        """Bulk delete files via direct access or Sandbox RPC."""
        if scope not in WRITABLE_SCOPES:
            return f"Error: Cannot delete from scope '{scope}'. Writable scopes: {', '.join(sorted(WRITABLE_SCOPES))}"

        if not paths:
            return "Error: No paths specified"

        if self.workspace:
            # Direct mode - delete from filesystem
            succeeded = []
            failed = []
            for p in paths:
                try:
                    validated_path = get_scoped_path(self.workspace, scope, p)
                    path_obj = Path(validated_path)
                    if not path_obj.exists():
                        failed.append({"path": p, "error": "File not found"})
                    else:
                        path_obj.unlink()
                        succeeded.append(p)
                except Exception as e:
                    failed.append({"path": p, "error": str(e)})
            return self._format_bulk_result(succeeded, failed)
        elif self.sandbox:
            # RPC mode - call sandbox
            try:
                result = self.sandbox.delete_files.remote(scope=scope, paths=paths)
                return self._format_bulk_result(result.get("succeeded", []), result.get("failed", []))
            except Exception as e:
                return f"Error during bulk delete: {e}"
        else:
            return "Error: Tool not configured (no workspace or sandbox)"

    def _format_bulk_result(self, succeeded: list, failed: list) -> str:
        output = []
        if succeeded:
            output.append(f"Successfully deleted {len(succeeded)} file(s):")
            for p in succeeded:
                output.append(f"  - '{p}'")
        if failed:
            output.append(f"Failed to delete {len(failed)} file(s):")
            for f in failed:
                output.append(f"  - '{f['path']}': {f['error']}")
        return "\n".join(output) if output else "No files processed"


class RenameFileInput(BaseModel):
    """Input schema for RenameFileTool."""

    scope: str = Field(
        description="The scope directory (frontend, dbml, test-case). "
        "Note: 'prototype' is read-only."
    )
    old_path: str = Field(description="The current relative path of the file")
    new_path: str = Field(description="The new relative path for the file")


class RenameFileTool(BaseTool):
    """Tool for renaming/moving files within the project workspace."""

    name: str = "rename_file"
    description: str = (
        "Rename or move a file within the project. Both old and new paths must be "
        "in the same scope. Use scope='frontend' for generated code, "
        "'dbml' for database schemas, 'test-case' for tests. "
        "Note: 'prototype' is read-only."
    )
    args_schema: type[BaseModel] = RenameFileInput

    # One of these must be set
    workspace: str | None = None  # For direct mode
    sandbox: Any = None  # For RPC mode

    def _run(self, scope: str, old_path: str, new_path: str) -> str:
        """Rename file via direct access or Sandbox RPC."""
        if scope not in WRITABLE_SCOPES:
            return f"Error: Cannot rename in scope '{scope}'. Writable scopes: {', '.join(sorted(WRITABLE_SCOPES))}"

        if self.workspace:
            # Direct mode - rename on filesystem
            # Note: S3 Mountpoint doesn't support rename, use copy+delete
            try:
                validated_old = get_scoped_path(self.workspace, scope, old_path)
                validated_new = get_scoped_path(self.workspace, scope, new_path)
                old_file = Path(validated_old)
                new_file = Path(validated_new)

                if not old_file.exists():
                    return f"Error: File '{old_path}' not found in scope '{scope}'"

                new_file.parent.mkdir(parents=True, exist_ok=True)
                # Use copy+delete for S3 Mountpoint compatibility
                shutil.copy2(old_file, new_file)
                old_file.unlink()

                # Verify the rename succeeded
                if not new_file.exists():
                    return f"Error: Rename failed - '{new_path}' was not created"
                if old_file.exists():
                    return f"Error: Rename failed - '{old_path}' still exists after delete"

                return f"Successfully renamed '{old_path}' to '{new_path}' in scope '{scope}'"
            except Exception as e:
                return f"Error renaming file: {e}"
        elif self.sandbox:
            # RPC mode - call sandbox
            try:
                self.sandbox.rename_file.remote(scope=scope, old_path=old_path, new_path=new_path)
                return f"Successfully renamed '{old_path}' to '{new_path}' in scope '{scope}'"
            except FileNotFoundError:
                return f"Error: File '{old_path}' not found in scope '{scope}'"
            except Exception as e:
                return f"Error renaming file: {e}"
        else:
            return "Error: Tool not configured (no workspace or sandbox)"


class RenameFilesInput(BaseModel):
    """Input schema for RenameFilesTool."""

    scope: str = Field(
        description="The scope directory (frontend, dbml, test-case). "
        "Note: 'prototype' is read-only."
    )
    renames: list[tuple[str, str]] = Field(
        description="List of (old_path, new_path) tuples to rename"
    )


class RenameFilesTool(BaseTool):
    """Tool for bulk renaming/moving files within the project workspace."""

    name: str = "rename_files"
    description: str = (
        "Bulk rename or move multiple files within the project. Use this instead of "
        "calling rename_file multiple times. Each rename is (old_path, new_path). "
        "All paths must be in the same scope. Returns detailed success/failure info. "
        "Note: 'prototype' is read-only."
    )
    args_schema: type[BaseModel] = RenameFilesInput

    # One of these must be set
    workspace: str | None = None  # For direct mode
    sandbox: Any = None  # For RPC mode

    def _run(self, scope: str, renames: list[tuple[str, str]]) -> str:
        """Bulk rename files via direct access or Sandbox RPC."""
        if scope not in WRITABLE_SCOPES:
            return f"Error: Cannot rename in scope '{scope}'. Writable scopes: {', '.join(sorted(WRITABLE_SCOPES))}"

        if not renames:
            return "Error: No renames specified"

        if self.workspace:
            # Direct mode - rename on filesystem
            succeeded = []
            failed = []
            for old_path, new_path in renames:
                try:
                    validated_old = get_scoped_path(self.workspace, scope, old_path)
                    validated_new = get_scoped_path(self.workspace, scope, new_path)
                    old_file = Path(validated_old)
                    new_file = Path(validated_new)

                    if not old_file.exists():
                        failed.append({"old_path": old_path, "error": "File not found"})
                        continue

                    new_file.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(old_file, new_file)
                    old_file.unlink()
                    succeeded.append((old_path, new_path))
                except Exception as e:
                    failed.append({"old_path": old_path, "new_path": new_path, "error": str(e)})
            return self._format_bulk_result(succeeded, failed)
        elif self.sandbox:
            # RPC mode - call sandbox
            try:
                result = self.sandbox.rename_files.remote(scope=scope, renames=renames)
                return self._format_bulk_result(result.get("succeeded", []), result.get("failed", []))
            except Exception as e:
                return f"Error during bulk rename: {e}"
        else:
            return "Error: Tool not configured (no workspace or sandbox)"

    def _format_bulk_result(self, succeeded: list, failed: list) -> str:
        output = []
        if succeeded:
            output.append(f"Successfully renamed {len(succeeded)} file(s):")
            for old, new in succeeded:
                output.append(f"  - '{old}' -> '{new}'")
        if failed:
            output.append(f"Failed to rename {len(failed)} file(s):")
            for f in failed:
                output.append(f"  - '{f['old_path']}': {f['error']}")
        return "\n".join(output) if output else "No files processed"


class RunCommandInput(BaseModel):
    """Input schema for RunCommandTool."""

    command: str = Field(description="The shell command to run")
    cwd: str | None = Field(
        default=None,
        description="Working directory relative to workspace (e.g., 'frontend', 'frontend/src'). "
        "Defaults to workspace root.",
    )


class RunCommandTool(BaseTool):
    """Tool for running shell commands in the sandbox workspace."""

    name: str = "run_command"
    description: str = (
        "Run a shell command in the sandbox workspace. Use this for running build "
        "commands, linters, tests, or other CLI tools. Commands run in a sandboxed "
        "environment with a 30-second timeout. "
        "IMPORTANT: Do NOT use this for file operations (create, write, delete, rename). "
        "Use write_file, delete_file, and rename_file tools instead - they work reliably "
        "with cloud storage. "
        "Available directories: prototype (read-only), frontend, dbml, test-case."
    )
    args_schema: type[BaseModel] = RunCommandInput

    # One of these must be set
    workspace: str | None = None  # For direct mode
    sandbox: Any = None  # For RPC mode

    def _run(self, command: str, cwd: str | None = None) -> str:
        """Run command via direct execution or Sandbox RPC."""
        if self.workspace:
            # Direct mode - run locally
            try:
                work_dir = Path(self.workspace)
                if cwd:
                    work_dir = work_dir / cwd
                    # Security: ensure we stay within workspace
                    if not str(work_dir.resolve()).startswith(self.workspace):
                        return "Error: Cannot execute outside workspace"

                result = subprocess.run(
                    command,
                    shell=True,
                    cwd=str(work_dir),
                    capture_output=True,
                    text=True,
                    timeout=30,
                )

                output = []
                if result.stdout:
                    output.append(f"stdout:\n{result.stdout}")
                if result.stderr:
                    output.append(f"stderr:\n{result.stderr}")
                output.append(f"exit code: {result.returncode}")
                return "\n".join(output) if output else "Command completed with no output"
            except subprocess.TimeoutExpired:
                return "Error: Command timed out after 30 seconds"
            except Exception as e:
                return f"Error running command: {e}"
        elif self.sandbox:
            # RPC mode - call sandbox
            try:
                result = self.sandbox.run_command.remote(command=command, cwd=cwd)
                output = []
                if result["stdout"]:
                    output.append(f"stdout:\n{result['stdout']}")
                if result["stderr"]:
                    output.append(f"stderr:\n{result['stderr']}")
                output.append(f"exit code: {result['returncode']}")
                return "\n".join(output) if output else "Command completed with no output"
            except Exception as e:
                return f"Error running command: {e}"
        else:
            return "Error: Tool not configured (no workspace or sandbox)"


def create_direct_tools(workspace: str) -> list[BaseTool]:
    """
    Create all agent tools configured for direct filesystem access.

    Use this when running inside the container with direct access to the workspace.

    Args:
        workspace: Path to the workspace directory (e.g., "/root/workspace/user/project").

    Returns:
        List of configured LangChain tools.
    """
    return [
        ReadFileTool(workspace=workspace),
        WriteFileTool(workspace=workspace),
        ListFilesTool(workspace=workspace),
        DeleteFileTool(workspace=workspace),
        DeleteFilesTool(workspace=workspace),
        RenameFileTool(workspace=workspace),
        RenameFilesTool(workspace=workspace),
        RunCommandTool(workspace=workspace),
    ]


def create_rpc_tools(sandbox: Any) -> list[BaseTool]:
    """
    Create all agent tools configured for Sandbox RPC access.

    Use this when running outside the container and need to use RPC calls.

    Args:
        sandbox: A Modal Sandbox reference for RPC calls.

    Returns:
        List of configured LangChain tools.
    """
    return [
        ReadFileTool(sandbox=sandbox),
        WriteFileTool(sandbox=sandbox),
        ListFilesTool(sandbox=sandbox),
        DeleteFileTool(sandbox=sandbox),
        DeleteFilesTool(sandbox=sandbox),
        RenameFileTool(sandbox=sandbox),
        RenameFilesTool(sandbox=sandbox),
        RunCommandTool(sandbox=sandbox),
    ]


def create_tools(*, workspace: str | None = None, sandbox: Any = None) -> list[BaseTool]:
    """
    Create all agent tools in direct mode (workspace) or RPC mode (sandbox).

    Args:
        workspace: Path for direct filesystem access (inside container).
        sandbox: Modal sandbox reference for RPC access (outside container).

    Returns:
        List of configured LangChain tools.

    Raises:
        ValueError: If both or neither parameters are provided.
    """
    if workspace and sandbox:
        raise ValueError("Specify workspace OR sandbox, not both")

    if workspace:
        return create_direct_tools(workspace)
    elif sandbox:
        return create_rpc_tools(sandbox)
    else:
        raise ValueError("Must specify workspace or sandbox")

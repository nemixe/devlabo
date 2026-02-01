"""LangChain-compatible tools for file operations via Sandbox RPC."""

import logging
from typing import Any

from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


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
    sandbox: Any = None

    def _run(self, scope: str, path: str) -> str:
        """Read file via Sandbox RPC."""
        if self.sandbox is None:
            return "Error: Sandbox not initialized"
        try:
            return self.sandbox.read_file.remote(scope=scope, relative_path=path)
        except FileNotFoundError:
            return f"Error: File '{path}' not found in scope '{scope}'"
        except Exception as e:
            return f"Error reading file: {e}"


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
    sandbox: Any = None

    # Scopes the agent is allowed to write to
    WRITABLE_SCOPES: frozenset[str] = frozenset({"frontend", "dbml", "test-case"})

    def _run(self, scope: str, path: str, content: str) -> str:
        """Write file via Sandbox RPC. CloudBucketMount handles R2 persistence."""
        if self.sandbox is None:
            return "Error: Sandbox not initialized"

        # Prevent writing to prototype (read-only source of truth)
        if scope not in self.WRITABLE_SCOPES:
            return f"Error: Cannot write to scope '{scope}'. Writable scopes: {', '.join(sorted(self.WRITABLE_SCOPES))}"

        try:
            self.sandbox.write_file.remote(scope=scope, relative_path=path, content=content)
            return f"Successfully wrote '{path}' to scope '{scope}'"
        except Exception as e:
            return f"Error writing file: {e}"


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
    sandbox: Any = None

    def _run(self, scope: str) -> str:
        """List files via Sandbox RPC."""
        if self.sandbox is None:
            return "Error: Sandbox not initialized"
        try:
            files = self.sandbox.list_files.remote(scope=scope)
            if not files:
                return f"No files found in scope '{scope}'"
            return f"Files in '{scope}':\n" + "\n".join(f"  - {f}" for f in sorted(files))
        except Exception as e:
            return f"Error listing files: {e}"


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
    sandbox: Any = None

    # Scopes the agent is allowed to delete from
    WRITABLE_SCOPES: frozenset[str] = frozenset({"frontend", "dbml", "test-case"})

    def _run(self, scope: str, path: str) -> str:
        """Delete file via Sandbox RPC. CloudBucketMount handles R2 persistence."""
        if self.sandbox is None:
            return "Error: Sandbox not initialized"

        if scope not in self.WRITABLE_SCOPES:
            return f"Error: Cannot delete from scope '{scope}'. Writable scopes: {', '.join(sorted(self.WRITABLE_SCOPES))}"

        try:
            self.sandbox.delete_file.remote(scope=scope, relative_path=path)
            return f"Successfully deleted '{path}' from scope '{scope}'"
        except FileNotFoundError:
            return f"Error: File '{path}' not found in scope '{scope}'"
        except Exception as e:
            return f"Error deleting file: {e}"


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
    sandbox: Any = None

    # Scopes the agent is allowed to delete from
    WRITABLE_SCOPES: frozenset[str] = frozenset({"frontend", "dbml", "test-case"})

    def _run(self, scope: str, paths: list[str]) -> str:
        """Bulk delete files via Sandbox RPC."""
        if self.sandbox is None:
            return "Error: Sandbox not initialized"

        if scope not in self.WRITABLE_SCOPES:
            return f"Error: Cannot delete from scope '{scope}'. Writable scopes: {', '.join(sorted(self.WRITABLE_SCOPES))}"

        if not paths:
            return "Error: No paths specified"

        try:
            result = self.sandbox.delete_files.remote(scope=scope, paths=paths)
            succeeded = result.get("succeeded", [])
            failed = result.get("failed", [])

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
        except Exception as e:
            return f"Error during bulk delete: {e}"


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
    sandbox: Any = None

    # Scopes the agent is allowed to rename in
    WRITABLE_SCOPES: frozenset[str] = frozenset({"frontend", "dbml", "test-case"})

    def _run(self, scope: str, old_path: str, new_path: str) -> str:
        """Rename file via Sandbox RPC. CloudBucketMount handles R2 persistence."""
        if self.sandbox is None:
            return "Error: Sandbox not initialized"

        if scope not in self.WRITABLE_SCOPES:
            return f"Error: Cannot rename in scope '{scope}'. Writable scopes: {', '.join(sorted(self.WRITABLE_SCOPES))}"

        try:
            self.sandbox.rename_file.remote(scope=scope, old_path=old_path, new_path=new_path)
            return f"Successfully renamed '{old_path}' to '{new_path}' in scope '{scope}'"
        except FileNotFoundError:
            return f"Error: File '{old_path}' not found in scope '{scope}'"
        except Exception as e:
            return f"Error renaming file: {e}"


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
    sandbox: Any = None

    # Scopes the agent is allowed to rename in
    WRITABLE_SCOPES: frozenset[str] = frozenset({"frontend", "dbml", "test-case"})

    def _run(self, scope: str, renames: list[tuple[str, str]]) -> str:
        """Bulk rename files via Sandbox RPC."""
        if self.sandbox is None:
            return "Error: Sandbox not initialized"

        if scope not in self.WRITABLE_SCOPES:
            return f"Error: Cannot rename in scope '{scope}'. Writable scopes: {', '.join(sorted(self.WRITABLE_SCOPES))}"

        if not renames:
            return "Error: No renames specified"

        try:
            result = self.sandbox.rename_files.remote(scope=scope, renames=renames)
            succeeded = result.get("succeeded", [])
            failed = result.get("failed", [])

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
        except Exception as e:
            return f"Error during bulk rename: {e}"


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
    sandbox: Any = None

    def _run(self, command: str, cwd: str | None = None) -> str:
        """Run command via Sandbox RPC."""
        if self.sandbox is None:
            return "Error: Sandbox not initialized"

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


def create_tools(sandbox: Any) -> list[BaseTool]:
    """
    Create all agent tools configured with the given sandbox.

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

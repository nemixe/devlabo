"""Tests for agent tools."""

import pytest

from agent.tools import (
    DeleteFileTool,
    DeleteFilesTool,
    ListFilesTool,
    ReadFileTool,
    RenameFileTool,
    RenameFilesTool,
    RunCommandTool,
    WriteFileTool,
    create_direct_tools,
    create_rpc_tools,
    create_tools,
)


class MockSandbox:
    """Mock Sandbox for testing tools."""

    def __init__(self):
        self.files = {
            "prototype": {"index.html": "<h1>Hello</h1>"},
            "frontend": {"src/App.tsx": "export default function App() {}"},
            "dbml": {},
            "test-case": {},
        }

    class MockRemoteMethod:
        def __init__(self, func):
            self.func = func

        def remote(self, **kwargs):
            return self.func(**kwargs)

    @property
    def read_file(self):
        def _read_file(scope: str, relative_path: str) -> str:
            if scope not in self.files:
                raise ValueError(f"Invalid scope: {scope}")
            if relative_path not in self.files[scope]:
                raise FileNotFoundError(f"File not found: {relative_path}")
            return self.files[scope][relative_path]

        return self.MockRemoteMethod(_read_file)

    @property
    def write_file(self):
        def _write_file(scope: str, relative_path: str, content: str) -> bool:
            if scope not in self.files:
                self.files[scope] = {}
            self.files[scope][relative_path] = content
            return True

        return self.MockRemoteMethod(_write_file)

    @property
    def list_files(self):
        def _list_files(scope: str) -> list[str]:
            if scope not in self.files:
                return []
            return list(self.files[scope].keys())

        return self.MockRemoteMethod(_list_files)

    @property
    def delete_file(self):
        def _delete_file(scope: str, relative_path: str) -> bool:
            if scope not in self.files:
                raise ValueError(f"Invalid scope: {scope}")
            if relative_path not in self.files[scope]:
                raise FileNotFoundError(f"File not found: {relative_path}")
            del self.files[scope][relative_path]
            return True

        return self.MockRemoteMethod(_delete_file)

    @property
    def delete_files(self):
        def _delete_files(scope: str, paths: list[str]) -> dict:
            if scope not in self.files:
                return {"succeeded": [], "failed": [{"path": p, "error": f"Invalid scope: {scope}"} for p in paths]}
            succeeded = []
            failed = []
            for path in paths:
                if path in self.files[scope]:
                    del self.files[scope][path]
                    succeeded.append(path)
                else:
                    failed.append({"path": path, "error": f"File not found: {path}"})
            return {"succeeded": succeeded, "failed": failed}

        return self.MockRemoteMethod(_delete_files)

    @property
    def rename_file(self):
        def _rename_file(scope: str, old_path: str, new_path: str) -> bool:
            if scope not in self.files:
                raise ValueError(f"Invalid scope: {scope}")
            if old_path not in self.files[scope]:
                raise FileNotFoundError(f"File not found: {old_path}")
            self.files[scope][new_path] = self.files[scope].pop(old_path)
            return True

        return self.MockRemoteMethod(_rename_file)

    @property
    def rename_files(self):
        def _rename_files(scope: str, renames: list[tuple[str, str]]) -> dict:
            if scope not in self.files:
                return {"succeeded": [], "failed": [{"old_path": old, "new_path": new, "error": f"Invalid scope: {scope}"} for old, new in renames]}
            succeeded = []
            failed = []
            for old_path, new_path in renames:
                if old_path in self.files[scope]:
                    self.files[scope][new_path] = self.files[scope].pop(old_path)
                    succeeded.append((old_path, new_path))
                else:
                    failed.append({"old_path": old_path, "new_path": new_path, "error": f"File not found: {old_path}"})
            return {"succeeded": succeeded, "failed": failed}

        return self.MockRemoteMethod(_rename_files)

    @property
    def run_command(self):
        def _run_command(command: str, cwd: str | None = None) -> dict:
            # Simple mock that just returns success
            return {"stdout": f"Executed: {command}", "stderr": "", "returncode": 0}

        return self.MockRemoteMethod(_run_command)


@pytest.fixture
def mock_sandbox():
    """Create a mock sandbox for testing."""
    return MockSandbox()


class TestReadFileTool:
    """Tests for ReadFileTool."""

    def test_read_existing_file(self, mock_sandbox):
        """Should successfully read an existing file."""
        tool = ReadFileTool(sandbox=mock_sandbox)
        result = tool._run(scope="prototype", path="index.html")
        assert result == "<h1>Hello</h1>"

    def test_read_nonexistent_file(self, mock_sandbox):
        """Should return error for non-existent file."""
        tool = ReadFileTool(sandbox=mock_sandbox)
        result = tool._run(scope="prototype", path="missing.html")
        assert "Error" in result
        assert "not found" in result

    def test_read_no_sandbox_or_workspace(self):
        """Should return error if neither sandbox nor workspace configured."""
        tool = ReadFileTool()
        result = tool._run(scope="prototype", path="index.html")
        assert "Error" in result
        assert "not configured" in result


class TestWriteFileTool:
    """Tests for WriteFileTool."""

    def test_write_to_frontend(self, mock_sandbox):
        """Should successfully write to frontend scope."""
        tool = WriteFileTool(sandbox=mock_sandbox)
        result = tool._run(scope="frontend", path="src/Button.tsx", content="button code")
        assert "Successfully wrote" in result
        assert mock_sandbox.files["frontend"]["src/Button.tsx"] == "button code"

    def test_write_to_dbml(self, mock_sandbox):
        """Should successfully write to dbml scope."""
        tool = WriteFileTool(sandbox=mock_sandbox)
        result = tool._run(scope="dbml", path="schema.dbml", content="Table users {}")
        assert "Successfully wrote" in result
        assert mock_sandbox.files["dbml"]["schema.dbml"] == "Table users {}"

    def test_write_to_test_case(self, mock_sandbox):
        """Should successfully write to test-case scope."""
        tool = WriteFileTool(sandbox=mock_sandbox)
        result = tool._run(scope="test-case", path="app.test.tsx", content="test code")
        assert "Successfully wrote" in result

    def test_write_to_prototype_blocked(self, mock_sandbox):
        """Should block writes to prototype (read-only)."""
        tool = WriteFileTool(sandbox=mock_sandbox)
        result = tool._run(scope="prototype", path="hack.html", content="hacked")
        assert "Error" in result
        assert "Cannot write to scope 'prototype'" in result
        # Ensure file was not written
        assert "hack.html" not in mock_sandbox.files["prototype"]

    def test_write_no_sandbox_or_workspace(self):
        """Should return error if neither sandbox nor workspace configured."""
        tool = WriteFileTool()
        result = tool._run(scope="frontend", path="test.txt", content="content")
        assert "Error" in result
        assert "not configured" in result


class TestListFilesTool:
    """Tests for ListFilesTool."""

    def test_list_files_with_content(self, mock_sandbox):
        """Should list files in a scope with content."""
        tool = ListFilesTool(sandbox=mock_sandbox)
        result = tool._run(scope="prototype")
        assert "index.html" in result

    def test_list_files_empty_scope(self, mock_sandbox):
        """Should handle empty scope."""
        tool = ListFilesTool(sandbox=mock_sandbox)
        result = tool._run(scope="dbml")
        assert "No files found" in result

    def test_list_no_sandbox_or_workspace(self):
        """Should return error if neither sandbox nor workspace configured."""
        tool = ListFilesTool()
        result = tool._run(scope="prototype")
        assert "Error" in result
        assert "not configured" in result


class TestDeleteFileTool:
    """Tests for DeleteFileTool."""

    def test_delete_existing_file(self, mock_sandbox):
        """Should successfully delete an existing file."""
        # First add a file to delete
        mock_sandbox.files["frontend"]["to_delete.txt"] = "delete me"
        tool = DeleteFileTool(sandbox=mock_sandbox)
        result = tool._run(scope="frontend", path="to_delete.txt")
        assert "Successfully deleted" in result
        assert "to_delete.txt" not in mock_sandbox.files["frontend"]

    def test_delete_nonexistent_file(self, mock_sandbox):
        """Should return error for non-existent file."""
        tool = DeleteFileTool(sandbox=mock_sandbox)
        result = tool._run(scope="frontend", path="missing.txt")
        assert "Error" in result
        assert "not found" in result

    def test_delete_from_prototype_blocked(self, mock_sandbox):
        """Should block deletes from prototype (read-only)."""
        tool = DeleteFileTool(sandbox=mock_sandbox)
        result = tool._run(scope="prototype", path="index.html")
        assert "Error" in result
        assert "Cannot delete from scope 'prototype'" in result
        # Ensure file was not deleted
        assert "index.html" in mock_sandbox.files["prototype"]

    def test_delete_no_sandbox_or_workspace(self):
        """Should return error if neither sandbox nor workspace configured."""
        tool = DeleteFileTool()
        result = tool._run(scope="frontend", path="test.txt")
        assert "Error" in result
        assert "not configured" in result


class TestRenameFileTool:
    """Tests for RenameFileTool."""

    def test_rename_existing_file(self, mock_sandbox):
        """Should successfully rename an existing file."""
        mock_sandbox.files["frontend"]["old_name.txt"] = "content"
        tool = RenameFileTool(sandbox=mock_sandbox)
        result = tool._run(scope="frontend", old_path="old_name.txt", new_path="new_name.txt")
        assert "Successfully renamed" in result
        assert "old_name.txt" not in mock_sandbox.files["frontend"]
        assert mock_sandbox.files["frontend"]["new_name.txt"] == "content"

    def test_rename_nonexistent_file(self, mock_sandbox):
        """Should return error for non-existent file."""
        tool = RenameFileTool(sandbox=mock_sandbox)
        result = tool._run(scope="frontend", old_path="missing.txt", new_path="new.txt")
        assert "Error" in result
        assert "not found" in result

    def test_rename_in_prototype_blocked(self, mock_sandbox):
        """Should block renames in prototype (read-only)."""
        tool = RenameFileTool(sandbox=mock_sandbox)
        result = tool._run(scope="prototype", old_path="index.html", new_path="main.html")
        assert "Error" in result
        assert "Cannot rename in scope 'prototype'" in result
        # Ensure file was not renamed
        assert "index.html" in mock_sandbox.files["prototype"]

    def test_rename_no_sandbox_or_workspace(self):
        """Should return error if neither sandbox nor workspace configured."""
        tool = RenameFileTool()
        result = tool._run(scope="frontend", old_path="a.txt", new_path="b.txt")
        assert "Error" in result
        assert "not configured" in result


class TestDeleteFilesTool:
    """Tests for DeleteFilesTool (bulk delete)."""

    def test_delete_multiple_files(self, mock_sandbox):
        """Should successfully delete multiple files."""
        mock_sandbox.files["frontend"]["a.txt"] = "a"
        mock_sandbox.files["frontend"]["b.txt"] = "b"
        mock_sandbox.files["frontend"]["c.txt"] = "c"
        tool = DeleteFilesTool(sandbox=mock_sandbox)
        result = tool._run(scope="frontend", paths=["a.txt", "b.txt"])
        assert "Successfully deleted 2 file(s)" in result
        assert "a.txt" not in mock_sandbox.files["frontend"]
        assert "b.txt" not in mock_sandbox.files["frontend"]
        assert "c.txt" in mock_sandbox.files["frontend"]  # Unchanged

    def test_delete_partial_failure(self, mock_sandbox):
        """Should report both successes and failures."""
        mock_sandbox.files["frontend"]["exists.txt"] = "content"
        tool = DeleteFilesTool(sandbox=mock_sandbox)
        result = tool._run(scope="frontend", paths=["exists.txt", "missing.txt"])
        assert "Successfully deleted 1 file(s)" in result
        assert "Failed to delete 1 file(s)" in result
        assert "missing.txt" in result

    def test_delete_from_prototype_blocked(self, mock_sandbox):
        """Should block deletes from prototype (read-only)."""
        tool = DeleteFilesTool(sandbox=mock_sandbox)
        result = tool._run(scope="prototype", paths=["index.html"])
        assert "Error" in result
        assert "Cannot delete from scope 'prototype'" in result

    def test_delete_no_sandbox_or_workspace(self):
        """Should return error if neither sandbox nor workspace configured."""
        tool = DeleteFilesTool()
        result = tool._run(scope="frontend", paths=["test.txt"])
        assert "Error" in result
        assert "not configured" in result


class TestRenameFilesTool:
    """Tests for RenameFilesTool (bulk rename)."""

    def test_rename_multiple_files(self, mock_sandbox):
        """Should successfully rename multiple files."""
        mock_sandbox.files["frontend"]["old1.txt"] = "content1"
        mock_sandbox.files["frontend"]["old2.txt"] = "content2"
        tool = RenameFilesTool(sandbox=mock_sandbox)
        result = tool._run(
            scope="frontend",
            renames=[("old1.txt", "new1.txt"), ("old2.txt", "new2.txt")]
        )
        assert "Successfully renamed 2 file(s)" in result
        assert "old1.txt" not in mock_sandbox.files["frontend"]
        assert "old2.txt" not in mock_sandbox.files["frontend"]
        assert mock_sandbox.files["frontend"]["new1.txt"] == "content1"
        assert mock_sandbox.files["frontend"]["new2.txt"] == "content2"

    def test_rename_partial_failure(self, mock_sandbox):
        """Should report both successes and failures."""
        mock_sandbox.files["frontend"]["exists.txt"] = "content"
        tool = RenameFilesTool(sandbox=mock_sandbox)
        result = tool._run(
            scope="frontend",
            renames=[("exists.txt", "renamed.txt"), ("missing.txt", "new.txt")]
        )
        assert "Successfully renamed 1 file(s)" in result
        assert "Failed to rename 1 file(s)" in result
        assert "missing.txt" in result

    def test_rename_in_prototype_blocked(self, mock_sandbox):
        """Should block renames in prototype (read-only)."""
        tool = RenameFilesTool(sandbox=mock_sandbox)
        result = tool._run(scope="prototype", renames=[("a.txt", "b.txt")])
        assert "Error" in result
        assert "Cannot rename in scope 'prototype'" in result

    def test_rename_no_sandbox_or_workspace(self):
        """Should return error if neither sandbox nor workspace configured."""
        tool = RenameFilesTool()
        result = tool._run(scope="frontend", renames=[("a.txt", "b.txt")])
        assert "Error" in result
        assert "not configured" in result


class TestRunCommandTool:
    """Tests for RunCommandTool."""

    def test_run_command_success(self, mock_sandbox):
        """Should successfully run a command."""
        tool = RunCommandTool(sandbox=mock_sandbox)
        result = tool._run(command="ls -la")
        assert "Executed: ls -la" in result
        assert "exit code: 0" in result

    def test_run_command_with_cwd(self, mock_sandbox):
        """Should run command with working directory."""
        tool = RunCommandTool(sandbox=mock_sandbox)
        result = tool._run(command="pwd", cwd="frontend")
        assert "exit code: 0" in result

    def test_run_command_no_sandbox_or_workspace(self):
        """Should return error if neither sandbox nor workspace configured."""
        tool = RunCommandTool()
        result = tool._run(command="ls")
        assert "Error" in result
        assert "not configured" in result


class TestCreateTools:
    """Tests for create_tools function."""

    def test_create_rpc_tools(self, mock_sandbox):
        """Should create all eight tools with sandbox (RPC mode)."""
        tools = create_tools(sandbox=mock_sandbox)
        assert len(tools) == 8

        tool_names = {t.name for t in tools}
        assert "read_file" in tool_names
        assert "write_file" in tool_names
        assert "list_files" in tool_names
        assert "delete_file" in tool_names
        assert "delete_files" in tool_names
        assert "rename_file" in tool_names
        assert "rename_files" in tool_names
        assert "run_command" in tool_names

    def test_tools_have_sandbox_reference(self, mock_sandbox):
        """All tools should have sandbox reference in RPC mode."""
        tools = create_tools(sandbox=mock_sandbox)
        for tool in tools:
            assert tool.sandbox is mock_sandbox
            assert tool.workspace is None

    def test_create_direct_tools_with_workspace(self, tmp_path):
        """Should create all eight tools with workspace (direct mode)."""
        workspace = str(tmp_path)
        tools = create_tools(workspace=workspace)
        assert len(tools) == 8

        for tool in tools:
            assert tool.workspace == workspace
            assert tool.sandbox is None

    def test_create_direct_tools_helper(self, tmp_path):
        """create_direct_tools should work same as create_tools(workspace=...)."""
        workspace = str(tmp_path)
        tools = create_direct_tools(workspace)
        assert len(tools) == 8
        for tool in tools:
            assert tool.workspace == workspace

    def test_create_rpc_tools_helper(self, mock_sandbox):
        """create_rpc_tools should work same as create_tools(sandbox=...)."""
        tools = create_rpc_tools(mock_sandbox)
        assert len(tools) == 8
        for tool in tools:
            assert tool.sandbox is mock_sandbox

    def test_create_tools_requires_exactly_one_arg(self, mock_sandbox, tmp_path):
        """create_tools should raise error if both or neither args provided."""
        # Neither provided
        with pytest.raises(ValueError, match="Must specify workspace or sandbox"):
            create_tools()

        # Both provided
        with pytest.raises(ValueError, match="Specify workspace OR sandbox, not both"):
            create_tools(workspace=str(tmp_path), sandbox=mock_sandbox)


class TestToolSchemas:
    """Tests for tool input schemas."""

    def test_read_file_schema(self):
        """ReadFileTool should have correct schema."""
        tool = ReadFileTool(sandbox=None)
        schema = tool.args_schema.model_json_schema()
        assert "scope" in schema["properties"]
        assert "path" in schema["properties"]

    def test_write_file_schema(self):
        """WriteFileTool should have correct schema."""
        tool = WriteFileTool(sandbox=None)
        schema = tool.args_schema.model_json_schema()
        assert "scope" in schema["properties"]
        assert "path" in schema["properties"]
        assert "content" in schema["properties"]

    def test_list_files_schema(self):
        """ListFilesTool should have correct schema."""
        tool = ListFilesTool(sandbox=None)
        schema = tool.args_schema.model_json_schema()
        assert "scope" in schema["properties"]

"""Tests for agent tools."""

from unittest.mock import MagicMock

import pytest

from agent.tools import ListFilesTool, ReadFileTool, WriteFileTool, create_tools


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

    def test_read_no_sandbox(self):
        """Should return error if sandbox not initialized."""
        tool = ReadFileTool(sandbox=None)
        result = tool._run(scope="prototype", path="index.html")
        assert "Error" in result
        assert "not initialized" in result


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

    def test_write_no_sandbox(self):
        """Should return error if sandbox not initialized."""
        tool = WriteFileTool(sandbox=None)
        result = tool._run(scope="frontend", path="test.txt", content="content")
        assert "Error" in result
        assert "not initialized" in result


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

    def test_list_no_sandbox(self):
        """Should return error if sandbox not initialized."""
        tool = ListFilesTool(sandbox=None)
        result = tool._run(scope="prototype")
        assert "Error" in result
        assert "not initialized" in result


class TestCreateTools:
    """Tests for create_tools function."""

    def test_creates_all_tools(self, mock_sandbox):
        """Should create all three tools."""
        tools = create_tools(mock_sandbox)
        assert len(tools) == 3

        tool_names = {t.name for t in tools}
        assert "read_file" in tool_names
        assert "write_file" in tool_names
        assert "list_files" in tool_names

    def test_tools_have_sandbox_reference(self, mock_sandbox):
        """All tools should have sandbox reference."""
        tools = create_tools(mock_sandbox)
        for tool in tools:
            assert tool.sandbox is mock_sandbox


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

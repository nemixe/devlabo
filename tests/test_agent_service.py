"""Tests for agent service."""

import pytest

from agent.prompts import (
    DBML_TRANSFORM_PROMPT,
    FRONTEND_TRANSFORM_PROMPT,
    SYSTEM_PROMPT,
    TEST_GENERATION_PROMPT,
)


class TestSystemPrompt:
    """Tests for system prompt content."""

    def test_system_prompt_has_tool_descriptions(self):
        """System prompt should describe available tools."""
        assert "list_files" in SYSTEM_PROMPT
        assert "read_file" in SYSTEM_PROMPT
        assert "write_file" in SYSTEM_PROMPT

    def test_system_prompt_has_scopes(self):
        """System prompt should mention all scopes."""
        assert "prototype" in SYSTEM_PROMPT
        assert "frontend" in SYSTEM_PROMPT
        assert "dbml" in SYSTEM_PROMPT
        assert "test-case" in SYSTEM_PROMPT

    def test_system_prompt_prototype_readonly(self):
        """System prompt should indicate prototype is read-only."""
        assert "READ ONLY" in SYSTEM_PROMPT or "read-only" in SYSTEM_PROMPT.lower()


class TestTransformPrompts:
    """Tests for transformation prompts."""

    def test_frontend_transform_prompt(self):
        """Frontend transform prompt should have React guidelines."""
        assert "React" in FRONTEND_TRANSFORM_PROMPT
        assert "functional components" in FRONTEND_TRANSFORM_PROMPT
        assert "Tailwind" in FRONTEND_TRANSFORM_PROMPT

    def test_dbml_transform_prompt(self):
        """DBML transform prompt should have schema guidelines."""
        assert "Table" in DBML_TRANSFORM_PROMPT
        assert "Ref" in DBML_TRANSFORM_PROMPT

    def test_test_generation_prompt(self):
        """Test generation prompt should have testing guidelines."""
        assert "Vitest" in TEST_GENERATION_PROMPT
        assert "describe" in TEST_GENERATION_PROMPT
        assert "expect" in TEST_GENERATION_PROMPT


class TestAgentServiceImports:
    """Tests for agent service module imports."""

    def test_can_import_agent_module(self):
        """Should be able to import agent module."""
        from agent import (
            FRONTEND_TRANSFORM_PROMPT,
            SYSTEM_PROMPT,
            ListFilesTool,
            ReadFileTool,
            WriteFileTool,
        )

        assert ReadFileTool is not None
        assert WriteFileTool is not None
        assert ListFilesTool is not None
        assert SYSTEM_PROMPT is not None
        assert FRONTEND_TRANSFORM_PROMPT is not None

    def test_can_import_tools_module(self):
        """Should be able to import tools module."""
        from agent.tools import create_tools

        assert callable(create_tools)

    def test_can_import_prompts_module(self):
        """Should be able to import prompts module."""
        from agent.prompts import (
            DBML_TRANSFORM_PROMPT,
            FRONTEND_TRANSFORM_PROMPT,
            SYSTEM_PROMPT,
            TEST_GENERATION_PROMPT,
        )

        # All prompts should be non-empty strings
        assert isinstance(SYSTEM_PROMPT, str) and len(SYSTEM_PROMPT) > 100
        assert isinstance(FRONTEND_TRANSFORM_PROMPT, str) and len(FRONTEND_TRANSFORM_PROMPT) > 50
        assert isinstance(DBML_TRANSFORM_PROMPT, str) and len(DBML_TRANSFORM_PROMPT) > 50
        assert isinstance(TEST_GENERATION_PROMPT, str) and len(TEST_GENERATION_PROMPT) > 50


class TestWritableScopes:
    """Tests for writable scope restrictions."""

    def test_writable_scopes_defined(self):
        """WRITABLE_SCOPES should be defined at module level."""
        from agent.tools import WRITABLE_SCOPES

        # WRITABLE_SCOPES is now a module-level constant
        assert "frontend" in WRITABLE_SCOPES
        assert "dbml" in WRITABLE_SCOPES
        assert "test-case" in WRITABLE_SCOPES
        # Prototype should NOT be writable
        assert "prototype" not in WRITABLE_SCOPES

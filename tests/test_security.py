"""Tests for security utilities."""

import pytest

from security.utils import (
    SecurityError,
    get_scoped_path,
    is_safe_filename,
    validate_path,
)


class TestValidatePath:
    """Tests for validate_path function."""

    def test_valid_relative_path(self, tmp_path):
        """Valid relative paths should resolve correctly."""
        base = str(tmp_path)
        result = validate_path(base, "subdir/file.txt")
        assert result == str(tmp_path / "subdir" / "file.txt")

    def test_valid_nested_path(self, tmp_path):
        """Deeply nested paths should work."""
        base = str(tmp_path)
        result = validate_path(base, "a/b/c/d/file.txt")
        assert result == str(tmp_path / "a" / "b" / "c" / "d" / "file.txt")

    def test_path_traversal_blocked(self, tmp_path):
        """Path traversal attempts should be blocked."""
        base = str(tmp_path)
        with pytest.raises(SecurityError, match="escapes base directory"):
            validate_path(base, "../escape.txt")

    def test_deep_traversal_blocked(self, tmp_path):
        """Deep path traversal attempts should be blocked."""
        base = str(tmp_path)
        with pytest.raises(SecurityError, match="escapes base directory"):
            validate_path(base, "subdir/../../escape.txt")

    def test_very_deep_traversal_blocked(self, tmp_path):
        """Very deep traversal attempts should be blocked."""
        base = str(tmp_path)
        with pytest.raises(SecurityError, match="escapes base directory"):
            validate_path(base, "a/b/c/../../../../escape.txt")

    def test_null_byte_blocked(self, tmp_path):
        """Null bytes in path should be blocked."""
        base = str(tmp_path)
        with pytest.raises(SecurityError, match="Null bytes"):
            validate_path(base, "file\x00.txt")

    def test_null_byte_in_base_blocked(self, tmp_path):
        """Null bytes in base directory should be blocked."""
        with pytest.raises(SecurityError, match="Null bytes"):
            validate_path(str(tmp_path) + "\x00", "file.txt")

    def test_empty_base_rejected(self):
        """Empty base directory should be rejected."""
        with pytest.raises(SecurityError, match="Base directory cannot be empty"):
            validate_path("", "file.txt")

    def test_empty_path_rejected(self, tmp_path):
        """Empty requested path should be rejected."""
        with pytest.raises(SecurityError, match="Requested path cannot be empty"):
            validate_path(str(tmp_path), "")

    def test_absolute_path_within_base(self, tmp_path):
        """Absolute paths within base should be allowed."""
        base = str(tmp_path)
        target = str(tmp_path / "subdir" / "file.txt")
        result = validate_path(base, target)
        assert result == target

    def test_absolute_path_outside_base_blocked(self, tmp_path):
        """Absolute paths outside base should be blocked."""
        base = str(tmp_path / "restricted")
        with pytest.raises(SecurityError, match="escapes base directory"):
            validate_path(base, "/etc/passwd")

    def test_symlink_resolution(self, tmp_path):
        """Symlinks should be resolved and validated."""
        # Create a directory structure
        subdir = tmp_path / "subdir"
        subdir.mkdir()

        # Create a file
        target_file = subdir / "target.txt"
        target_file.write_text("content")

        # The function should handle paths correctly
        result = validate_path(str(tmp_path), "subdir/target.txt")
        assert "subdir" in result
        assert "target.txt" in result


class TestIsSafeFilename:
    """Tests for is_safe_filename function."""

    def test_simple_filename(self):
        """Simple filenames should be safe."""
        assert is_safe_filename("file.txt") is True

    def test_filename_with_path(self):
        """Filenames with path components should be safe if no traversal."""
        assert is_safe_filename("src/components/Button.jsx") is True

    def test_dotdot_rejected(self):
        """Path traversal sequences should be rejected."""
        assert is_safe_filename("../file.txt") is False
        assert is_safe_filename("subdir/../file.txt") is False
        assert is_safe_filename("..") is False

    def test_double_slash_rejected(self):
        """Double slashes should be rejected."""
        assert is_safe_filename("path//file.txt") is False

    def test_null_byte_rejected(self):
        """Null bytes should be rejected."""
        assert is_safe_filename("file\x00.txt") is False

    def test_newline_rejected(self):
        """Newlines should be rejected."""
        assert is_safe_filename("file\n.txt") is False
        assert is_safe_filename("file\r.txt") is False

    def test_empty_rejected(self):
        """Empty filename should be rejected."""
        assert is_safe_filename("") is False

    def test_absolute_path_rejected(self):
        """Absolute paths should be rejected."""
        assert is_safe_filename("/etc/passwd") is False

    def test_tilde_rejected(self):
        """Home directory expansion should be rejected."""
        assert is_safe_filename("~/file.txt") is False

    def test_hidden_files_allowed(self):
        """Hidden files (single dot) should be allowed."""
        assert is_safe_filename(".gitignore") is True
        assert is_safe_filename(".env.example") is True

    def test_unicode_allowed(self):
        """Unicode characters should be allowed."""
        assert is_safe_filename("文件.txt") is True
        assert is_safe_filename("archivo.txt") is True


class TestGetScopedPath:
    """Tests for get_scoped_path function."""

    def test_basic_scoped_path(self, tmp_path):
        """Basic scoped path should resolve correctly."""
        workspace = str(tmp_path)
        result = get_scoped_path(workspace, "frontend", "src/App.jsx")
        expected = str(tmp_path / "frontend" / "src" / "App.jsx")
        assert result == expected

    def test_different_scopes(self, tmp_path):
        """Different scopes should resolve to different directories."""
        workspace = str(tmp_path)

        frontend_path = get_scoped_path(workspace, "frontend", "index.html")
        prototype_path = get_scoped_path(workspace, "prototype", "index.html")

        assert "frontend" in frontend_path
        assert "prototype" in prototype_path
        assert frontend_path != prototype_path

    def test_scope_escape_blocked(self, tmp_path):
        """Escaping the scope should be blocked."""
        workspace = str(tmp_path)
        with pytest.raises(SecurityError):
            get_scoped_path(workspace, "frontend", "../prototype/file.txt")

    def test_workspace_escape_blocked(self, tmp_path):
        """Escaping the workspace should be blocked."""
        workspace = str(tmp_path)
        with pytest.raises(SecurityError):
            get_scoped_path(workspace, "frontend", "../../escape.txt")

    def test_invalid_scope_rejected(self, tmp_path):
        """Invalid scope names should be rejected."""
        workspace = str(tmp_path)
        with pytest.raises(SecurityError, match="Invalid scope"):
            get_scoped_path(workspace, "../escape", "file.txt")

    def test_empty_workspace_rejected(self):
        """Empty workspace should be rejected."""
        with pytest.raises(SecurityError, match="Workspace cannot be empty"):
            get_scoped_path("", "frontend", "file.txt")

    def test_empty_scope_rejected(self, tmp_path):
        """Empty scope should be rejected."""
        with pytest.raises(SecurityError, match="Scope cannot be empty"):
            get_scoped_path(str(tmp_path), "", "file.txt")

    def test_empty_path_rejected(self, tmp_path):
        """Empty relative path should be rejected."""
        with pytest.raises(SecurityError, match="Relative path cannot be empty"):
            get_scoped_path(str(tmp_path), "frontend", "")

    def test_dangerous_relative_path_rejected(self, tmp_path):
        """Dangerous patterns in relative path should be rejected."""
        workspace = str(tmp_path)
        with pytest.raises(SecurityError, match="Unsafe filename"):
            get_scoped_path(workspace, "frontend", "file\x00.txt")

    def test_devlabo_scopes(self, tmp_path):
        """Test with actual DevLabo scope names."""
        workspace = str(tmp_path)

        # These are the actual scopes used in DevLabo
        scopes = ["prototype", "frontend", "dbml", "test-case"]

        for scope in scopes:
            result = get_scoped_path(workspace, scope, "index.html")
            assert scope in result
            assert result.startswith(workspace)

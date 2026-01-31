"""Path validation utilities to prevent path traversal attacks."""

import os
import re
from pathlib import Path


class SecurityError(Exception):
    """Raised when a security violation is detected."""

    pass


# Patterns that indicate potentially dangerous filenames
DANGEROUS_PATTERNS = [
    r"\.\.",  # Parent directory traversal
    r"//+",  # Multiple slashes
    r"\x00",  # Null bytes
    r"^/",  # Absolute paths (when not expected)
    r"^~",  # Home directory expansion
]

# Characters that should not appear in filenames
FORBIDDEN_CHARS = frozenset('\x00\n\r')


def validate_path(base_dir: str, requested_path: str) -> str:
    """
    Validates that requested_path stays within base_dir.

    Args:
        base_dir: The base directory that paths must stay within.
        requested_path: The path to validate (can be relative or absolute).

    Returns:
        Resolved absolute path that is guaranteed to be within base_dir.

    Raises:
        SecurityError: If the path escapes base_dir or contains dangerous patterns.
    """
    if not base_dir:
        raise SecurityError("Base directory cannot be empty")

    if not requested_path:
        raise SecurityError("Requested path cannot be empty")

    # Check for null bytes early
    if "\x00" in requested_path or "\x00" in base_dir:
        raise SecurityError("Null bytes detected in path")

    # Resolve the base directory to an absolute path
    base_path = Path(base_dir).resolve()

    # Join and resolve the requested path
    if os.path.isabs(requested_path):
        # For absolute paths, check if they're within base_dir
        target_path = Path(requested_path).resolve()
    else:
        # For relative paths, join with base_dir
        target_path = (base_path / requested_path).resolve()

    # Verify the resolved path is within the base directory
    try:
        target_path.relative_to(base_path)
    except ValueError as e:
        raise SecurityError(
            f"Path '{requested_path}' escapes base directory '{base_dir}'"
        ) from e

    return str(target_path)


def is_safe_filename(filename: str) -> bool:
    """
    Checks if a filename is safe to use.

    A safe filename:
    - Does not contain path traversal sequences (..)
    - Does not contain null bytes or newlines
    - Does not contain multiple consecutive slashes
    - Is not empty

    Args:
        filename: The filename to check.

    Returns:
        True if the filename is safe, False otherwise.
    """
    if not filename:
        return False

    # Check for forbidden characters
    if any(char in filename for char in FORBIDDEN_CHARS):
        return False

    # Check for dangerous patterns
    for pattern in DANGEROUS_PATTERNS:
        if re.search(pattern, filename):
            return False

    return True


def get_scoped_path(workspace: str, scope: str, relative_path: str) -> str:
    """
    Returns a validated path within a specific scope of the workspace.

    This function is designed for the DevLabo architecture where the AI agent
    has restricted access to specific folders (prototype, frontend, dbml, test-case).

    Args:
        workspace: The root workspace directory (e.g., "/root/workspace").
        scope: The subdirectory scope (e.g., "frontend", "prototype").
        relative_path: The relative path within the scope (e.g., "src/App.jsx").

    Returns:
        Validated absolute path within the scoped directory.

    Raises:
        SecurityError: If the path escapes the scoped directory.

    Example:
        >>> get_scoped_path("/workspace", "frontend", "src/App.jsx")
        '/workspace/frontend/src/App.jsx'
    """
    if not workspace:
        raise SecurityError("Workspace cannot be empty")

    if not scope:
        raise SecurityError("Scope cannot be empty")

    if not relative_path:
        raise SecurityError("Relative path cannot be empty")

    # Validate the scope itself doesn't contain traversal
    if not is_safe_filename(scope):
        raise SecurityError(f"Invalid scope: '{scope}'")

    # Validate the relative path doesn't contain obviously dangerous patterns
    if not is_safe_filename(relative_path):
        raise SecurityError(f"Unsafe filename pattern in: '{relative_path}'")

    # Build the scoped base directory
    scoped_base = os.path.join(workspace, scope)

    # Validate the final path stays within the scoped directory
    return validate_path(scoped_base, relative_path)

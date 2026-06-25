"""Repository-specific errors for file-backed Org documents."""

from __future__ import annotations

from dataclasses import dataclass


class RepositoryError(Exception):
    """Base repository error."""


@dataclass
class DocumentNotFoundError(RepositoryError):
    """Raised when a tracked Org document file is missing."""

    path: str

    def __str__(self) -> str:
        """Return the human-readable error message."""
        return f"File '{self.path}' not found"


@dataclass
class DocumentPermissionError(RepositoryError):
    """Raised when the repository cannot access a tracked file."""

    path: str

    def __str__(self) -> str:
        """Return the human-readable error message."""
        return f"Permission denied for '{self.path}'"


@dataclass
class DocumentParseError(RepositoryError):
    """Raised when a tracked file cannot be parsed as Org data."""

    path: str
    detail: str

    def __str__(self) -> str:
        """Return the human-readable error message."""
        return f"Unable to parse '{self.path}': {self.detail}"


@dataclass
class DocumentMissingError(RepositoryError):
    """Raised when a previously tracked file no longer exists."""

    path: str

    def __str__(self) -> str:
        """Return the human-readable error message."""
        return f"Tracked file '{self.path}' no longer exists"


@dataclass
class DocumentConflictError(RepositoryError):
    """Raised when a dirty document was changed outside the CLI."""

    path: str

    def __str__(self) -> str:
        """Return the human-readable error message."""
        return f"File '{self.path}' was modified outside of the CLI while it has in-memory changes"


@dataclass
class HeadingNotFoundError(RepositoryError):
    """Raised when a heading cannot be resolved by identity."""

    detail: str

    def __str__(self) -> str:
        """Return the human-readable error message."""
        return self.detail


@dataclass
class HeadingAmbiguousError(RepositoryError):
    """Raised when a heading selector resolves to multiple headings."""

    detail: str

    def __str__(self) -> str:
        """Return the human-readable error message."""
        return self.detail

"""Errors for query language parsing and execution."""


class QueryLanguageError(Exception):
    """Base exception for query language failures."""


class QueryParseError(QueryLanguageError):
    """Raised when query text cannot be parsed."""


class QueryRuntimeError(QueryLanguageError):
    """Raised when query execution fails at runtime."""

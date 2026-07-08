"""Library-specific errors."""

from __future__ import annotations


class LibraryError(Exception):
    """Base library error."""


class DocumentNotFoundError(LibraryError):
    """Requested document was not found."""


class DuplicateDocumentError(LibraryError):
    """Document with the same source SHA-256 already exists in the collection."""


class ExtractionError(LibraryError):
    """Failed to extract text from the source file."""


class UnsupportedFileTypeError(LibraryError):
    """File extension is not supported for extraction."""


class ScopeNotFoundError(LibraryError):
    """Knowledge scope was not found."""


class ScopeAccessDeniedError(LibraryError):
    """Authenticated user cannot access the requested knowledge scope."""


class CollectionNotFoundError(LibraryError):
    """DEPRECATED: pre-knowledge_scopes. Use ScopeNotFoundError instead.
    Collection was not found in library_collections_legacy."""


class UserNotFoundError(LibraryError):
    """Referenced user was not found."""

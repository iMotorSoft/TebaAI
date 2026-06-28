from __future__ import annotations


class DatabaseError(Exception):
    """Base exception for all database-related errors."""


class DatabaseConfigurationError(DatabaseError):
    """Raised when database settings cannot be resolved."""


class DatabaseConnectionError(DatabaseError):
    """Raised when a connection or pool cannot be established."""


class DatabasePoolNotInitializedError(DatabaseError):
    """Raised when attempting to use the pool before initialization."""


class DatabaseExecutionError(DatabaseError):
    """Raised when a database query execution fails."""


class DatabaseMigrationError(DatabaseError):
    """Raised when a migration operation fails."""

from __future__ import annotations


class RepositoryError(RuntimeError):
    """Base exception for persistence-layer errors that should not leak vendor-specific exceptions."""


class RepositoryConflictError(RepositoryError):
    pass


class RepositoryNotFoundError(RepositoryError):
    pass


class RepositoryUnavailableError(RepositoryError):
    pass

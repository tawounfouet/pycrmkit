"""Backend-safe SQLAlchemy error translation for PyCRMKit repositories."""

from __future__ import annotations

from sqlalchemy.exc import DBAPIError, IntegrityError, SQLAlchemyError

from pycrmkit.exceptions import DuplicateError, PyCRMKitError, RepositoryError


def translate_sqlalchemy_error(error: SQLAlchemyError) -> PyCRMKitError:
    """Translate backend/driver exceptions into stable PyCRMKit persistence errors."""

    context = _safe_context(error)
    sqlstate = context.get("sqlstate")

    if isinstance(error, IntegrityError):
        if sqlstate == "23505":
            return DuplicateError(
                "A persistence uniqueness constraint was violated",
                code="repository.duplicate",
                context=context,
            )
        if sqlstate == "23503":
            return RepositoryError(
                "A persistence foreign-key constraint was violated",
                code="repository.foreign_key_violation",
                context=context,
            )
        if sqlstate == "23502":
            return RepositoryError(
                "A required persistence value is missing",
                code="repository.not_null_violation",
                context=context,
            )
        if sqlstate == "23514":
            return RepositoryError(
                "A persistence check constraint was violated",
                code="repository.check_violation",
                context=context,
            )
        return RepositoryError(
            "A persistence integrity constraint was violated",
            code="repository.integrity_error",
            context=context,
        )

    if sqlstate == "40001":
        return RepositoryError(
            "The database transaction could not be serialized",
            code="repository.serialization_failure",
            context=context,
        )
    if sqlstate == "40P01":
        return RepositoryError(
            "The database transaction was aborted after a deadlock",
            code="repository.deadlock",
            context=context,
        )

    return RepositoryError(
        "The SQLAlchemy persistence operation failed",
        code="repository.backend_error",
        context=context,
    )


def _safe_context(error: SQLAlchemyError) -> dict[str, object]:
    """Return driver-neutral diagnostic metadata without SQL text or values."""

    context: dict[str, object] = {}
    if not isinstance(error, DBAPIError):
        return context

    original = error.orig
    sqlstate = getattr(original, "sqlstate", None)
    if sqlstate is not None:
        context["sqlstate"] = str(sqlstate)

    diagnostic = getattr(original, "diag", None)
    if diagnostic is not None:
        constraint = getattr(diagnostic, "constraint_name", None)
        if constraint:
            context["constraint"] = str(constraint)
        table = getattr(diagnostic, "table_name", None)
        if table:
            context["table"] = str(table)
        column = getattr(diagnostic, "column_name", None)
        if column:
            context["column"] = str(column)

    return context


__all__ = ["translate_sqlalchemy_error"]

"""
custom_exception.py
-------------------
All domain-specific exceptions for the T-TESS AI Coaching Observer.

Usage
-----
    from common.custom_exception import (
        TTESSBaseException,
        ConfigurationError,
        OpenAIClientError,
        OpenAIRateLimitError,
        OpenAITimeoutError,
        InvalidObservationDataError,
        RubricParsingError,
    )
"""

from __future__ import annotations


# ---------------------------------------------------------------------------
# Base
# ---------------------------------------------------------------------------

class TTESSBaseException(Exception):
    """
    Root exception for the T-TESS Observer application.

    All custom exceptions inherit from this class so callers can catch the
    entire hierarchy with a single ``except TTESSBaseException`` clause when
    needed.
    """

    def __init__(self, message: str, *, detail: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.detail = detail

    def __str__(self) -> str:
        if self.detail:
            return f"{self.message} | detail: {self.detail}"
        return self.message


# ---------------------------------------------------------------------------
# Configuration errors
# ---------------------------------------------------------------------------

class ConfigurationError(TTESSBaseException):
    """
    Raised when a required configuration value is absent or invalid.

    Example
    -------
        raise ConfigurationError(
            "OPENAI_API_KEY is missing",
            detail="Add it to your .env file."
        )
    """


# ---------------------------------------------------------------------------
# OpenAI / network errors
# ---------------------------------------------------------------------------

class OpenAIClientError(TTESSBaseException):
    """
    Raised when the OpenAI API returns an unexpected or unrecoverable error.

    Wraps the original exception as ``cause`` for upstream logging.
    """

    def __init__(
        self,
        message: str,
        *,
        detail: str | None = None,
        cause: BaseException | None = None,
    ) -> None:
        super().__init__(message, detail=detail)
        self.cause = cause


class OpenAIRateLimitError(OpenAIClientError):
    """
    Raised specifically when the OpenAI API returns a 429 rate-limit response.

    Callers may choose to implement retry / back-off logic on this exception.
    """


class OpenAITimeoutError(OpenAIClientError):
    """
    Raised when a request to the OpenAI API times out.
    """


# ---------------------------------------------------------------------------
# Domain / data errors
# ---------------------------------------------------------------------------

class InvalidObservationDataError(TTESSBaseException):
    """
    Raised when observation form data fails validation before being sent to
    the AI model (e.g., missing required fields, out-of-range scores).

    Parameters
    ----------
    message:
        Human-readable description of what is invalid.
    field:
        Optional name of the specific field that failed validation.
    """

    def __init__(
        self,
        message: str,
        *,
        detail: str | None = None,
        field: str | None = None,
    ) -> None:
        super().__init__(message, detail=detail)
        self.field = field

    def __str__(self) -> str:
        base = super().__str__()
        if self.field:
            return f"[field={self.field}] {base}"
        return base


class RubricParsingError(TTESSBaseException):
    """
    Raised when the AI response cannot be parsed into a structured
    T-TESS rubric result (e.g., malformed JSON or missing dimension keys).
    """
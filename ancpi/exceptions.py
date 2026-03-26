"""Custom exceptions for ANCPI client."""


class ANCPIError(Exception):
    """Base exception for ANCPI client errors."""


class ServiceUnavailableError(ANCPIError):
    """All server paths returned errors (typically 502 Proxy Error)."""

    def __init__(self, theme: str, tried_paths: list[str]):
        self.theme = theme
        self.tried_paths = tried_paths
        paths = ", ".join(tried_paths)
        super().__init__(
            f"Service unavailable for {theme}. "
            f"Tried paths: {paths}. "
            f"The ANCPI server may be temporarily down — try again later."
        )


class QueryError(ANCPIError):
    """Server returned an error response to our query."""

    def __init__(self, code: int, message: str, details: list[str] | None = None):
        self.code = code
        self.error_message = message
        self.details = details or []
        super().__init__(f"ANCPI query error {code}: {message}")


class NoResultsError(ANCPIError):
    """Query returned no features."""

    def __init__(self, query_description: str):
        self.query_description = query_description
        super().__init__(f"No results found for: {query_description}")

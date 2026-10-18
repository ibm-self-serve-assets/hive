import logging

# Routes whose successful (2xx/3xx) access log lines are suppressed.
# Errors (4xx/5xx) are always shown.
_SILENT_PATHS = frozenset([
    "/api/stream",
    "/api/csrf",
    "/api/config",
    "/api/status",
])


class QuietPollFilter(logging.Filter):
    """
    Filters out access log records for high-frequency polling routes.
    Keeps error responses (status >= 400) visible regardless of path.
    """
    def filter(self, record: logging.LogRecord) -> bool:
        status = getattr(record, "status_code", 200)
        if status >= 400:
            return True
        msg = record.getMessage()
        return not any(
            f'"{path} HTTP' in msg or f'"{path}?' in msg
            for path in _SILENT_PATHS
        )

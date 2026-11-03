class AdminConflictError(Exception):
    """The action is not allowed in the target's current state (HTTP 409)."""


class AdminInputError(Exception):
    """The request body or upload is invalid as a whole (HTTP 400)."""

    def __init__(self, message: str, *, extra: dict | None = None):
        super().__init__(message)
        self.extra = extra or {}

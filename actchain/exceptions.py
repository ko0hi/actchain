class ActchainError(Exception):
    """Base class for exceptions in actchain."""

    pass


class UnsupportedError(ActchainError):
    """Raised when an unsupported operation is attempted."""

    pass


class InvalidOverrideError(ActchainError):
    """Raised when an invalid override is attempted."""

    pass

import better_exceptions

better_exceptions.hook()


class ActchainError(Exception):
    """Base class for exceptions in actchain."""

    pass


class InvalidOverrideError(ActchainError):
    """Raised when an invalid override is attempted."""

    pass


class EventHandleError(ActchainError):
    """Raised when an event is failed to be handled."""

    pass


class ChainableAlreadyRunningError(ActchainError):
    """Raised when a chainable is already running."""

    pass


class UnsupportedOperationError(ActchainError):
    """Raised when an unsupported operation is attempted."""

    pass

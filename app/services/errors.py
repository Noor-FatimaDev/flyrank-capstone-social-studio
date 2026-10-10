class ServiceError(Exception):
    """Base class for expected errors. Each subclass carries its HTTP status."""

    status_code = 400


class NotFoundError(ServiceError):
    status_code = 404


class ConflictError(ServiceError):
    """The request is valid, but the resource's current state does not allow it."""

    status_code = 409


class ValidationFailedError(ServiceError):
    """The submitted text breaks a platform's constraint profile."""

    status_code = 422
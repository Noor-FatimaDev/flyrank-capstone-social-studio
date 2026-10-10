class ServiceError(Exception):
    """Base class for expected errors. Each subclass carries its HTTP status."""

    status_code = 400


class NotFoundError(ServiceError):
    status_code = 404
class DomainError(Exception):
    http_status = 400


class NotFound(DomainError):
    http_status = 404


class Forbidden(DomainError):
    http_status = 403


class Conflict(DomainError):
    http_status = 409

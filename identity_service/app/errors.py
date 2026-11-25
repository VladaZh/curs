class DomainError(Exception):
    http_status = 400


class InvalidInput(DomainError):
    http_status = 400


class InvalidCredentials(DomainError):
    http_status = 401


class InvalidToken(DomainError):
    http_status = 401


class Forbidden(DomainError):
    http_status = 403


class NotFound(DomainError):
    http_status = 404


class Conflict(DomainError):
    http_status = 409


class AccountLocked(DomainError):
    http_status = 429

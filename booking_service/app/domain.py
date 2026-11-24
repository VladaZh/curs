from enum import StrEnum
from typing import Protocol, Sequence


class BookingStatus(StrEnum):
    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    SEATED = "SEATED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"
    NO_SHOW = "NO_SHOW"


ACTIVE_STATUSES = (BookingStatus.PENDING, BookingStatus.CONFIRMED, BookingStatus.SEATED)

S = BookingStatus
TRANSITIONS: dict[BookingStatus, set[BookingStatus]] = {
    S.PENDING: {S.CONFIRMED, S.CANCELLED, S.EXPIRED},
    S.CONFIRMED: {S.SEATED, S.CANCELLED, S.NO_SHOW},
    S.SEATED: {S.COMPLETED},
    S.COMPLETED: set(),
    S.CANCELLED: set(),
    S.EXPIRED: set(),
    S.NO_SHOW: set(),
}


class DomainError(Exception):
    http_status = 400


class NotFound(DomainError):
    http_status = 404


class Forbidden(DomainError):
    http_status = 403


class NoAvailability(DomainError):
    http_status = 409


class InvalidTransition(DomainError):
    http_status = 409


class HoldExpired(DomainError):
    http_status = 410


def ensure_transition(current: BookingStatus, new: BookingStatus) -> None:
    if new not in TRANSITIONS[current]:
        raise InvalidTransition(f"Нельзя перейти из {current} в {new}")


class TableLike(Protocol):
    id: object
    capacity: int


class TableSelectionStrategy(Protocol):
    def order(
        self, tables: Sequence[TableLike], party_size: int
    ) -> list[TableLike]: ...


class BestFitStrategy:

    def order(self, tables, party_size):
        return sorted(tables, key=lambda t: (t.capacity, str(t.id)))

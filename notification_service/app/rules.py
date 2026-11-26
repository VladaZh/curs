from dataclasses import dataclass
from datetime import datetime, timedelta

from .events import BookingEvent

REMINDER_CANCEL_TOPICS = frozenset(
    {
        "booking.cancelled",
        "booking.expired",
        "booking.seated",
        "booking.completed",
        "booking.no_show",
    }
)


@dataclass(frozen=True)
class Plan:
    kind: str
    channel: str
    send_after: datetime


def plan_notifications(
    topic: str, ev: BookingEvent, now: datetime, reminder_hours: int, sms_enabled: bool
) -> list[Plan]:
    if topic == "booking.confirmed":
        plans = [Plan("booking_confirmed", "email", now)]
        remind_at = ev.starts_at - timedelta(hours=reminder_hours)
        if remind_at > now:
            plans.append(Plan("booking_reminder", "email", remind_at))
            if sms_enabled:
                plans.append(Plan("booking_reminder", "sms", remind_at))
        return plans
    if topic == "booking.cancelled":
        return [Plan("booking_cancelled", "email", now)]
    return []

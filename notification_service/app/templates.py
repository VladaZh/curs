from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo


@dataclass(frozen=True)
class RenderedMessage:
    subject: str
    body: str


_TEMPLATES: dict[tuple[str, str], tuple[str, str]] = {
    ("booking_confirmed", "email"): (
        "Бронь подтверждена: {restaurant}",
        "Здравствуйте, {name}!\n\nВаш столик в «{restaurant}» подтверждён.\n"
        "Дата: {date}\nВремя: {time}\nГостей: {party}\n\n"
        "Если планы изменились, пожалуйста, отмените бронь заранее.",
    ),
    ("booking_reminder", "email"): (
        "Напоминание о брони: {restaurant}, {date} в {time}",
        "Здравствуйте, {name}!\n\nНапоминаем, что вас ждут в «{restaurant}» {date} в {time}.\n"
        "Гостей: {party}.",
    ),
    ("booking_reminder", "sms"): (
        "",
        "«{restaurant}»: напоминаем о брони {date} в {time}, гостей: {party}.",
    ),
    ("booking_cancelled", "email"): (
        "Бронь отменена: {restaurant}",
        "Здравствуйте, {name}!\n\nВаша бронь в «{restaurant}» на {date} в {time} отменена.",
    ),
}


def render(
    kind: str,
    channel: str,
    *,
    name: str,
    restaurant: str,
    timezone: str,
    starts_at: datetime,
    party_size: int
) -> RenderedMessage:
    subject_t, body_t = _TEMPLATES[(kind, channel)]
    local = starts_at.astimezone(ZoneInfo(timezone))
    ctx = {
        "name": name,
        "restaurant": restaurant,
        "party": party_size,
        "date": local.strftime("%d.%m.%Y"),
        "time": local.strftime("%H:%M"),
    }
    subject = subject_t.format_map(ctx)
    return RenderedMessage(" ".join(subject.split()), body_t.format_map(ctx))

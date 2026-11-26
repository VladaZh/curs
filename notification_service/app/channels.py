import logging
from email.message import EmailMessage
from typing import Protocol

from .config import Settings
from .templates import RenderedMessage

log = logging.getLogger("notification.channels")


class PermanentError(Exception):...


class Channel(Protocol):
    async def send(self, to: str, message: RenderedMessage, idempotency_key: str) -> None: ...


def _mask(addr: str) -> str:
    return addr[:2] + "***" if len(addr) > 2 else "***"


class LogChannel:
    def __init__(self, name: str):
        self.name = name

    async def send(self, to, message, idempotency_key):
        log.info("[%s] to=%s subject=%r body=%r", self.name, _mask(to), message.subject, message.body)


class SmtpEmailChannel:
    def __init__(self, s: Settings):
        self.s = s

    async def send(self, to, message, idempotency_key):
        import aiosmtplib

        em = EmailMessage()
        em["From"], em["To"], em["Subject"] = self.s.smtp_from, to, message.subject
        em["Message-ID"] = f"<{idempotency_key}@notification.local>"
        em.set_content(message.body)
        try:
            await aiosmtplib.send(em, hostname=self.s.smtp_host, port=self.s.smtp_port,
                                  username=self.s.smtp_username, password=self.s.smtp_password,
                                  start_tls=self.s.smtp_starttls, timeout=15)
        except aiosmtplib.SMTPRecipientsRefused as e:
            raise PermanentError(str(e)) from e


def build_channels(s: Settings) -> dict[str, Channel]:
    return {
        "email": SmtpEmailChannel(s) if s.smtp_host else LogChannel("email"),
        "sms": LogChannel("sms"),
    }

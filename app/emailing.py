from __future__ import annotations

import json
import smtplib
import ssl
from dataclasses import dataclass
from email.message import EmailMessage as SMTPMessage
from pathlib import Path
from typing import Protocol
from uuid import uuid4


class EmailDeliveryError(RuntimeError):
    pass


@dataclass(frozen=True)
class EmailDeliveryResult:
    message_id: str
    provider: str
    accepted: bool
    recipient: str
    detail: str = ""


class EmailProvider(Protocol):
    provider_id: str

    def send(self, *, to: str, subject: str, text: str) -> EmailDeliveryResult: ...


class ConsoleEmailProvider:
    """Development-safe provider that writes messages to an outbox JSONL file.

    It never claims external delivery. This keeps invitation/password-reset flows testable
    without SMTP credentials and avoids silently dropping security-sensitive messages.
    """

    provider_id = "console"

    def __init__(self, outbox_path: str = "data/email_outbox.jsonl"):
        self.path = Path(outbox_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def send(self, *, to: str, subject: str, text: str) -> EmailDeliveryResult:
        message_id = f"MAIL-{uuid4().hex[:18].upper()}"
        record = {
            "message_id": message_id,
            "provider": self.provider_id,
            "to": to,
            "subject": subject,
            "text": text,
            "externally_delivered": False,
        }
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
        return EmailDeliveryResult(
            message_id=message_id,
            provider=self.provider_id,
            accepted=True,
            recipient=to,
            detail="stored in local outbox; not externally delivered",
        )


class SMTPEmailProvider:
    provider_id = "smtp"

    def __init__(
        self,
        *,
        host: str,
        port: int,
        username: str = "",
        password: str = "",
        sender: str,
        use_tls: bool = True,
        use_ssl: bool = False,
        timeout_seconds: int = 20,
    ):
        if not host or not sender:
            raise EmailDeliveryError("SMTP host and sender are required")
        self.host = host
        self.port = int(port)
        self.username = username
        self.password = password
        self.sender = sender
        self.use_tls = bool(use_tls)
        self.use_ssl = bool(use_ssl)
        self.timeout_seconds = int(timeout_seconds)

    def send(self, *, to: str, subject: str, text: str) -> EmailDeliveryResult:
        message_id = f"MAIL-{uuid4().hex[:18].upper()}"
        msg = SMTPMessage()
        msg["From"] = self.sender
        msg["To"] = to
        msg["Subject"] = subject
        msg["Message-ID"] = f"<{message_id.lower()}@careeros.local>"
        msg.set_content(text)
        try:
            if self.use_ssl:
                context = ssl.create_default_context()
                client = smtplib.SMTP_SSL(self.host, self.port, timeout=self.timeout_seconds, context=context)
            else:
                client = smtplib.SMTP(self.host, self.port, timeout=self.timeout_seconds)
            with client:
                client.ehlo()
                if self.use_tls and not self.use_ssl:
                    client.starttls(context=ssl.create_default_context())
                    client.ehlo()
                if self.username:
                    client.login(self.username, self.password)
                refused = client.send_message(msg)
            if refused:
                raise EmailDeliveryError(f"SMTP refused recipients: {sorted(refused)}")
        except Exception as exc:
            if isinstance(exc, EmailDeliveryError):
                raise
            raise EmailDeliveryError(f"SMTP delivery failed: {exc}") from exc
        return EmailDeliveryResult(
            message_id=message_id,
            provider=self.provider_id,
            accepted=True,
            recipient=to,
            detail="accepted by SMTP server",
        )


def build_email_provider(
    provider: str,
    *,
    outbox_path: str = "data/email_outbox.jsonl",
    smtp_host: str = "",
    smtp_port: int = 587,
    smtp_username: str = "",
    smtp_password: str = "",
    email_from: str = "",
    smtp_use_tls: bool = True,
    smtp_use_ssl: bool = False,
    timeout_seconds: int = 20,
) -> EmailProvider:
    normalized = (provider or "console").strip().lower()
    if normalized == "console":
        return ConsoleEmailProvider(outbox_path)
    if normalized == "smtp":
        return SMTPEmailProvider(
            host=smtp_host,
            port=smtp_port,
            username=smtp_username,
            password=smtp_password,
            sender=email_from,
            use_tls=smtp_use_tls,
            use_ssl=smtp_use_ssl,
            timeout_seconds=timeout_seconds,
        )
    raise EmailDeliveryError(f"unsupported email provider: {provider}")


def invitation_email(*, product_name: str, invite_url: str, role: str, expires_at: str) -> tuple[str, str]:
    subject = f"{product_name} invitation"
    text = (
        f"You have been invited to {product_name}.\n\n"
        f"Role: {role}\n"
        f"Accept invitation: {invite_url}\n"
        f"Expires: {expires_at}\n\n"
        "If you were not expecting this invitation, you can ignore this message."
    )
    return subject, text


def password_reset_email(*, product_name: str, reset_url: str, ttl_minutes: int) -> tuple[str, str]:
    subject = f"{product_name} password reset"
    text = (
        f"A password reset was requested for your {product_name} account.\n\n"
        f"Reset password: {reset_url}\n"
        f"This link expires in approximately {ttl_minutes} minutes.\n\n"
        "If you did not request this, ignore this message."
    )
    return subject, text

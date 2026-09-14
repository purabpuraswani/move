"""Sending the password reset email over SMTP.

Standard library only (smtplib + email.message), so no new dependency. The
send runs as a FastAPI background task after the response has gone, which
keeps the forgot-password response time the same whether or not the address
belongs to an account.
"""

import logging
import smtplib
import ssl
from email.message import EmailMessage
from urllib.parse import quote

import config


logger = logging.getLogger("movewell.password_reset")


def reset_link(token: str) -> str:
    return f"{config.FRONTEND_URL}/reset-password?token={quote(token, safe='')}"


def build_reset_email(to_address: str, name: str, token: str) -> EmailMessage:
    link = reset_link(token)
    minutes = config.PASSWORD_RESET_TOKEN_MINUTES
    greeting = f"Hi {name}," if name else "Hi,"

    message = EmailMessage()
    message["Subject"] = "Reset your MoveWell AI password"
    message["From"] = config.SMTP_FROM
    message["To"] = to_address

    message.set_content(
        f"{greeting}\n\n"
        "We received a request to reset the password for your MoveWell AI account.\n\n"
        f"Choose a new password here (the link works once and expires in {minutes} minutes):\n\n"
        f"{link}\n\n"
        "If you did not ask for this, you can ignore this email. Your password will not change.\n\n"
        "MoveWell AI\n"
    )

    return message


def _deliver(message: EmailMessage) -> None:
    if config.SMTP_SECURITY == "ssl":
        with smtplib.SMTP_SSL(
            config.SMTP_HOST, config.SMTP_PORT,
            context=ssl.create_default_context(), timeout=20,
        ) as server:
            if config.SMTP_USERNAME:
                server.login(config.SMTP_USERNAME, config.SMTP_PASSWORD or "")
            server.send_message(message)
        return

    with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=20) as server:
        if config.SMTP_SECURITY == "starttls":
            server.starttls(context=ssl.create_default_context())
        if config.SMTP_USERNAME:
            server.login(config.SMTP_USERNAME, config.SMTP_PASSWORD or "")
        server.send_message(message)


def send_reset_email(to_address: str, name: str, token: str) -> None:
    """Deliver the reset email. Never raises: it runs after the response."""

    if not config.smtp_configured():
        if config.PASSWORD_RESET_LOG_LINKS:
            logger.warning(
                "SMTP is not configured; PASSWORD_RESET_LOG_LINKS is on, so the "
                "reset link is logged instead of emailed (development only): %s",
                reset_link(token),
            )
        else:
            logger.error(
                "A password reset was requested but no email was sent: set "
                "SMTP_HOST and SMTP_FROM in backend/.env."
            )
        return

    try:
        _deliver(build_reset_email(to_address, name, token))
    except (smtplib.SMTPException, OSError) as error:
        # The address is deliberately not logged with the failure.
        logger.error(
            "Password reset email could not be sent: %s: %s",
            type(error).__name__, error,
        )

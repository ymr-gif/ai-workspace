import asyncio
import logging
import smtplib
from email.mime.text import MIMEText

from config import SMTP_FROM, SMTP_HOST, SMTP_PASSWORD, SMTP_PORT, SMTP_STARTTLS, SMTP_USERNAME

logger = logging.getLogger("services.email")


async def send_email(to: str, subject: str, body: str) -> None:
    if not SMTP_HOST or not to:
        logger.debug("[email] skipped — no host or recipient")
        return

    msg = MIMEText(body, _subtype="plain", _charset="utf-8")
    msg["Subject"] = subject
    msg["From"] = SMTP_FROM or SMTP_USERNAME
    msg["To"] = to

    def _send():
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15) as s:
            # Fail-closed by default: an "only if advertised" check is downgradeable
            # (a MITM can strip the STARTTLS capability from EHLO). Plain dev relays
            # (MailHog) opt out explicitly via SMTP_STARTTLS=false.
            if SMTP_PORT != 465 and SMTP_STARTTLS:
                s.starttls()
            if SMTP_USERNAME:
                s.login(SMTP_USERNAME, SMTP_PASSWORD)
            s.send_message(msg)

    try:
        await asyncio.to_thread(_send)
        logger.info("[email] sent to=%s subject=%s", to, subject)
    except Exception as e:
        logger.warning("[email] failed to=%s err=%s", to, e)
        raise RuntimeError(f"send_email failed: {e}") from e

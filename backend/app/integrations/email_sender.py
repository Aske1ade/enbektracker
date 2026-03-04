from app.core.config import settings
from app.utils import send_email


def send_notification_email(*, email_to: str, subject: str, body: str) -> None:
    if not settings.emails_enabled:
        return
    send_email(email_to=email_to, subject=subject, html_content=body)

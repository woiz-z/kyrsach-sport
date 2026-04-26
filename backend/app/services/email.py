import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import aiosmtplib

from app.config import get_settings

logger = logging.getLogger(__name__)


async def send_password_reset_email(to_email: str, reset_link: str) -> None:
    settings = get_settings()

    if not settings.SMTP_USER or not settings.SMTP_PASSWORD:
        logger.warning("SMTP not configured – skipping password reset email to %s", to_email)
        return

    msg = MIMEMultipart("alternative")
    msg["Subject"] = "Скидання пароля – SportPredict AI"
    msg["From"] = settings.SMTP_FROM or settings.SMTP_USER
    msg["To"] = to_email

    plain = (
        f"Ви отримали цей лист, тому що надіслали запит на скидання пароля.\n\n"
        f"Для скидання пароля перейдіть за посиланням:\n{reset_link}\n\n"
        f"Посилання дійсне протягом 1 години.\n\n"
        f"Якщо ви не надсилали цей запит – просто ігноруйте цей лист."
    )

    html = f"""
    <html>
      <body style="font-family: Arial, sans-serif; background: #f1f5f9; padding: 32px;">
        <div style="max-width: 480px; margin: 0 auto; background: #fff;
                    border-radius: 16px; padding: 40px; box-shadow: 0 4px 24px #0001;">
          <h2 style="color: #1e40af; margin-bottom: 8px;">SportPredict AI</h2>
          <h3 style="color: #1e293b; margin-top: 0;">Скидання пароля</h3>
          <p style="color: #475569;">
            Ви отримали цей лист, тому що надіслали запит на скидання пароля.
          </p>
          <a href="{reset_link}"
             style="display: inline-block; margin: 24px 0; padding: 14px 32px;
                    background: linear-gradient(135deg, #2563eb, #10b981);
                    color: #fff; text-decoration: none; border-radius: 10px;
                    font-weight: bold; font-size: 16px;">
            Скинути пароль
          </a>
          <p style="color: #94a3b8; font-size: 13px;">
            Посилання дійсне протягом <strong>1 години</strong>.<br>
            Якщо ви не надсилали цей запит – просто ігноруйте цей лист.
          </p>
        </div>
      </body>
    </html>
    """

    msg.attach(MIMEText(plain, "plain"))
    msg.attach(MIMEText(html, "html"))

    try:
        await aiosmtplib.send(
            msg,
            hostname=settings.SMTP_HOST,
            port=settings.SMTP_PORT,
            username=settings.SMTP_USER,
            password=settings.SMTP_PASSWORD,
            start_tls=True,
        )
        logger.info("Password reset email sent to %s", to_email)
    except Exception as exc:
        logger.error("Failed to send password reset email to %s: %s", to_email, exc)
        raise

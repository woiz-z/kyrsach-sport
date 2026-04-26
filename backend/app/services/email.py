import asyncio
import json
import logging
import urllib.request

logger = logging.getLogger(__name__)

# Google Apps Script relay — Railway blocks outbound SMTP (port 587).
# GAS sends the email from Google's infra via a deployed Apps Script web app.
_GAS_URL = (
    "https://script.google.com/macros/s/"
    "AKfycbwl7zn7gRHTFS2eNFCP08b3iRMSFMYOyYIzGpRBi8kBVfQyTl4zIprbZqYxuzHQUWmQ/exec"
)


def _send_via_gas(to_email: str, reset_link: str) -> None:
    """Blocking HTTP POST to Google Apps Script email relay."""
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
    payload = json.dumps({
        "to": to_email,
        "subject": "Скидання пароля – SportPredict AI",
        "html": html,
        "secret": "WORKHIVE_SECRET_2026",
    }).encode("utf-8")
    req = urllib.request.Request(
        _GAS_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        body = resp.read().decode("utf-8", errors="replace")
    logger.info("Password-reset email sent to %s via GAS. Response: %s", to_email, body[:200])


async def send_password_reset_email(to_email: str, reset_link: str) -> None:
    loop = asyncio.get_event_loop()
    try:
        await loop.run_in_executor(None, _send_via_gas, to_email, reset_link)
    except Exception as exc:
        logger.error("Failed to send password reset email to %s via GAS: %s", to_email, exc)

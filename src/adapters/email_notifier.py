import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from src.config import env


def send_mail(html_body: str, subject: str) -> None:
    if not env.GMAIL_USER or not env.GMAIL_PASS or not env.EMAIL_TO:
        raise ValueError("Missing GMAIL_USER, GMAIL_PASS, or EMAIL_TO environment variables")

    recipients = [addr.strip() for addr in env.EMAIL_TO.split(",") if addr.strip()]
    if not recipients:
        raise ValueError("EMAIL_TO does not contain any valid recipients")

    message = MIMEMultipart("alternative")
    message["Subject"] = subject
    message["From"] = env.GMAIL_USER
    message["To"] = ", ".join(recipients)
    message.attach(MIMEText(html_body, "html", "utf-8"))

    use_ssl = env.SMTP_USE_SSL or env.SMTP_PORT == 465
    smtp_cls = smtplib.SMTP_SSL if use_ssl else smtplib.SMTP
    logging.info(
        "Sending email to %s via %s:%s (ssl=%s)",
        ", ".join(recipients),
        env.SMTP_SERVER,
        env.SMTP_PORT,
        use_ssl,
    )
    with smtp_cls(env.SMTP_SERVER, env.SMTP_PORT, timeout=30) as server:
        if not use_ssl:
            server.starttls()
        server.login(env.GMAIL_USER, env.GMAIL_PASS)
        server.sendmail(env.GMAIL_USER, recipients, message.as_string())

import logging
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from src.config import env


def send_mail(html_body: str, subject: str) -> None:
    if not env.GMAIL_USER or not env.GMAIL_PASS or not env.EMAIL_TO:
        raise ValueError("Missing GMAIL_USER, GMAIL_PASS, or EMAIL_TO environment variables")

    recipients = [addr.strip() for addr in env.EMAIL_TO.split(",") if addr.strip()]
    cc_recipients = [addr.strip() for addr in os.getenv("EMAIL_CC", "").split(",") if addr.strip()]
    bcc_recipients = [addr.strip() for addr in os.getenv("EMAIL_BCC", "").split(",") if addr.strip()]
    all_recipients = recipients + cc_recipients + bcc_recipients
    if not recipients:
        raise ValueError("EMAIL_TO does not contain any valid recipients")
    for addr in all_recipients:
        if "gmai.com" in addr.lower():
            logging.warning("suspicious email domain detected: %s did you mean gmail.com?", addr)

    message = MIMEMultipart("alternative")
    message["Subject"] = subject
    message["From"] = env.GMAIL_USER
    message["To"] = ", ".join(recipients)
    if cc_recipients:
        message["Cc"] = ", ".join(cc_recipients)
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
        server.sendmail(env.GMAIL_USER, all_recipients, message.as_string())

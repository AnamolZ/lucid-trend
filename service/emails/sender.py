"""Low-level SMTP email transport client."""

import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

def send_noreply_email(to_email: str, subject: str, body_html: str, smtp_server: str, smtp_user: str, smtp_password: str) -> bool:
    """Dispatches a MIME multipart HTML email using TLS over SMTP port 587."""
    smtp_port = 587
    sender_email = "no-reply@newspluk.com"
    sender_name = "NewsPluk Team"

    msg = MIMEMultipart()
    msg['From'] = f"{sender_name} <{sender_email}>"
    msg['To'] = to_email
    msg['Subject'] = subject
    msg.attach(MIMEText(body_html, 'html'))

    try:
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(smtp_user, smtp_password)
        server.sendmail(sender_email, to_email, msg.as_string())
        server.quit()
        logging.info(f"[EmailSender] Email sent successfully to {to_email}")
        return True
    except Exception as e:
        logging.error(f"[EmailSender] Failed to send email to {to_email}: {e}")
        return False

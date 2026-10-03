"""Low-level SMTP email transport client supporting single and bulk delivery."""

import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

def send_noreply_email(to_email: str, subject: str, body_html: str, smtp_server: str, smtp_user: str, smtp_password: str) -> bool:
    """Dispatches a single MIME multipart HTML email using TLS over SMTP port 587."""
    smtp_port = 587
    sender_email = "no-reply@newspluk.com"
    sender_name = "NewsPluk Team"

    msg = MIMEMultipart()
    msg['From'] = f"{sender_name} <{sender_email}>"
    msg['To'] = to_email
    msg['Subject'] = subject
    msg.attach(MIMEText(body_html, 'html'))

    try:
        server = smtplib.SMTP(smtp_server, smtp_port, timeout=30)
        server.starttls()
        server.login(smtp_user, smtp_password)
        server.sendmail(sender_email, to_email, msg.as_string())
        server.quit()
        logging.info(f"[EmailSender] Email sent successfully to {to_email}")
        return True
    except Exception as e:
        logging.error(f"[EmailSender] Failed to send email to {to_email}: {e}")
        return False

def send_bulk_emails(email_entries: list, smtp_server: str, smtp_user: str, smtp_password: str) -> int:
    """Dispatches emails to multiple recipients reusing a single authenticated SMTP session."""
    if not email_entries:
        return 0

    smtp_port = 587
    sender_email = "no-reply@newspluk.com"
    sender_name = "NewsPluk Team"
    sent_count = 0

    try:
        server = smtplib.SMTP(smtp_server, smtp_port, timeout=30)
        server.starttls()
        server.login(smtp_user, smtp_password)

        for to_email, subject, body_html in email_entries:
            try:
                msg = MIMEMultipart()
                msg['From'] = f"{sender_name} <{sender_email}>"
                msg['To'] = to_email
                msg['Subject'] = subject
                msg.attach(MIMEText(body_html, 'html'))

                server.sendmail(sender_email, to_email, msg.as_string())
                sent_count += 1
                logging.info(f"[EmailSender] Dispatched newsletter to {to_email}")
            except Exception as item_err:
                logging.warning(f"[EmailSender] Failed to dispatch to {to_email}: {item_err}")

        server.quit()
    except Exception as conn_err:
        logging.error(f"[EmailSender] SMTP connection failed during bulk dispatch: {conn_err}")

    return sent_count

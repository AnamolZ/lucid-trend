
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

def send_noreply_email(to_email, subject, body_html, SMTP_SERVER, SMTP_USER, SMTP_PASSWORD):
    SMTP_PORT = 587
    SENDER_EMAIL = "no-reply@newspluk.com"
    SENDER_NAME = "NewsPluk Team"

    msg = MIMEMultipart()
    msg['From'] = f"{SENDER_NAME} <{SENDER_EMAIL}>"
    msg['To'] = to_email
    msg['Subject'] = subject
    msg.attach(MIMEText(body_html, 'html'))

    try:
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(SMTP_USER, SMTP_PASSWORD)
        server.sendmail(SENDER_EMAIL, to_email, msg.as_string())
        server.quit()
        print(f"Email sent successfully to {to_email}")
        return True
    except Exception as e:
        print(f"Failed to send email to {to_email}: {e}")
        return False

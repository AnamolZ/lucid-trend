
import smtplib
import json
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from service.mongodb.fetch_emails import get_verified_emails
from template.notify_subscriber import notify_subscriber_template
from service.data_cleaning.gemini import email_title, build_content_with_gemini

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
        return False
    
def notify_subscribers(model, MONGO_URI, SMTP_SERVER, SMTP_USER, SMTP_PASSWORD):
    with open("service/blog/extracted_data.json", "r", encoding="utf-8") as f:
        news_json = json.load(f)

    for e_address in get_verified_emails(MONGO_URI):
        news_content = build_content_with_gemini(news_json, model)
        ready_html_content = notify_subscriber_template(email_title(model), news_content, e_address)
        send_noreply_email(e_address, email_title(model), ready_html_content, SMTP_SERVER, SMTP_USER, SMTP_PASSWORD)
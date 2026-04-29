import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

GMAIL_USER = os.getenv("GMAIL_USER")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")


def send_confirmation_email(to_email: str, client_name: str, meeting_time: str) -> bool:
    if not GMAIL_USER or not GMAIL_APP_PASSWORD:
        print("Email not configured: missing GMAIL_USER or GMAIL_APP_PASSWORD")
        return False

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = "אישור פגישה עם AUTOBOT"
        msg["From"] = GMAIL_USER
        msg["To"] = to_email

        body = f"""שלום {client_name},

הפגישה שלך עם אריק מ-AUTOBOT אושרה!

מועד: {meeting_time}

אם צריך לשנות — פשוט ענה להודעה הזו.

בברכה,
צוות AUTOBOT"""

        msg.attach(MIMEText(body, "plain", "utf-8"))

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
            server.sendmail(GMAIL_USER, to_email, msg.as_string())

        print(f"Confirmation email sent to {to_email}")
        return True
    except Exception as e:
        print(f"Email send error: {e}")
        return False

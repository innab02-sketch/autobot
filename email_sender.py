import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


def send_confirmation_email(to_email: str, client_name: str, meeting_time: str) -> bool:
    gmail_user = os.getenv("GMAIL_USER")
    gmail_password = os.getenv("GMAIL_APP_PASSWORD")
    if not gmail_user or not gmail_password:
        print("Email not configured: missing GMAIL_USER or GMAIL_APP_PASSWORD")
        return False

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = "אישור פגישה עם AUTOBOT"
        msg["From"] = gmail_user
        msg["To"] = to_email

        body = f"""שלום {client_name},

הפגישה שלך עם אריק מ-AUTOBOT אושרה!

מועד: {meeting_time}

אם צריך לשנות — פשוט ענה להודעה הזו.

בברכה,
צוות AUTOBOT"""

        msg.attach(MIMEText(body, "plain", "utf-8"))

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(gmail_user, gmail_password)
            server.sendmail(gmail_user, to_email, msg.as_string())

        print(f"Confirmation email sent to {to_email}")
        return True
    except Exception as e:
        print(f"Email send error: {e}")
        return False

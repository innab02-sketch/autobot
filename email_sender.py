import os
import smtplib
import uuid
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders


def _build_ics(client_name: str, start_dt: datetime, end_dt: datetime, organizer_email: str) -> str:
    """Build an ICS calendar invite string."""
    uid = str(uuid.uuid4())
    now = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    # Convert Israel time to UTC (subtract 3 hours)
    utc_start = (start_dt - timedelta(hours=3)).strftime("%Y%m%dT%H%M%SZ")
    utc_end = (end_dt - timedelta(hours=3)).strftime("%Y%m%dT%H%M%SZ")

    ics = f"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//AUTOBOT//Meeting//HE
METHOD:REQUEST
BEGIN:VEVENT
UID:{uid}
DTSTAMP:{now}
DTSTART:{utc_start}
DTEND:{utc_end}
SUMMARY:שיחת ייעוץ עם אריק - AUTOBOT
DESCRIPTION:שיחת ייעוץ בנושא אוטומציות עסקיות.\\nאם צריך לשנות - ענה למייל הזה.
ORGANIZER;CN=AUTOBOT:mailto:{organizer_email}
LOCATION:שיחת טלפון / זום
STATUS:CONFIRMED
BEGIN:VALARM
TRIGGER:-PT60M
ACTION:DISPLAY
DESCRIPTION:תזכורת: שיחת ייעוץ עם אריק בעוד שעה
END:VALARM
END:VEVENT
END:VCALENDAR"""
    return ics


def send_confirmation_email(to_email: str, client_name: str, meeting_time: str, start_dt=None, end_dt=None) -> bool:
    """Send confirmation email with ICS calendar invite attached.
    
    Args:
        to_email: Client's email address
        client_name: Client's full name
        meeting_time: Human-readable meeting time string (e.g. "יום שלישי 05.05 בשעה 10:00")
        start_dt: datetime object for meeting start (optional, used for ICS)
        end_dt: datetime object for meeting end (optional, used for ICS)
    """
    gmail_user = os.getenv("GMAIL_USER")
    gmail_password = os.getenv("GMAIL_APP_PASSWORD")

    if not gmail_user or not gmail_password:
        print("Email not configured: missing GMAIL_USER or GMAIL_APP_PASSWORD")
        return False

    try:
        msg = MIMEMultipart("mixed")
        msg["Subject"] = "אישור פגישה עם AUTOBOT - " + meeting_time
        msg["From"] = f"AUTOBOT <{gmail_user}>"
        msg["To"] = to_email

        # Email body
        body = f"""שלום {client_name},

הפגישה שלך עם אריק מ-AUTOBOT אושרה!

מועד: {meeting_time}
נושא: שיחת ייעוץ בנושא אוטומציות עסקיות

אם צריך לשנות — פשוט ענה להודעה הזו.

בברכה,
צוות AUTOBOT
"""
        msg.attach(MIMEText(body, "plain", "utf-8"))

        # Attach ICS file if we have datetime objects
        if start_dt and end_dt:
            ics_content = _build_ics(client_name, start_dt, end_dt, gmail_user)
            ics_part = MIMEBase("text", "calendar", method="REQUEST")
            ics_part.set_payload(ics_content.encode("utf-8"))
            encoders.encode_base64(ics_part)
            ics_part.add_header("Content-Disposition", "attachment", filename="invite.ics")
            ics_part.add_header("Content-Type", "text/calendar; method=REQUEST; charset=UTF-8")
            msg.attach(ics_part)

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(gmail_user, gmail_password)
            server.sendmail(gmail_user, to_email, msg.as_string())

        print(f"Confirmation email with ICS sent to {to_email}")
        return True

    except Exception as e:
        print(f"Email send error: {e}")
        return False

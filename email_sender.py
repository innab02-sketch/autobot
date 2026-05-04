import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from datetime import datetime, timedelta


# Titan SMTP settings
SMTP_SERVER = "smtp.titan.email"
SMTP_PORT = 465
SMTP_USER = "info@autobotil.com"
SMTP_PASSWORD = os.getenv("TITAN_EMAIL_PASSWORD", "Autobot2026#")


def _build_ics(client_name: str, start_dt: datetime, end_dt: datetime) -> str:
    """Build an ICS calendar invite string."""
    utc_start = (start_dt - timedelta(hours=3)).strftime("%Y%m%dT%H%M%SZ")
    utc_end = (end_dt - timedelta(hours=3)).strftime("%Y%m%dT%H%M%SZ")
    now_utc = (datetime.now() - timedelta(hours=3)).strftime("%Y%m%dT%H%M%SZ")

    return f"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//AUTOBOT//Meeting//HE
CALSCALE:GREGORIAN
METHOD:REQUEST
BEGIN:VEVENT
DTSTART:{utc_start}
DTEND:{utc_end}
DTSTAMP:{now_utc}
ORGANIZER;CN=AUTOBOT:mailto:info@autobotil.com
SUMMARY:שיחת ייעוץ עם אריק - AUTOBOT
DESCRIPTION:שיחת ייעוץ בנושא אוטומציות עסקיות עם אריק מ-AUTOBOT
LOCATION:שיחת טלפון / זום
STATUS:CONFIRMED
END:VEVENT
END:VCALENDAR"""


def _build_html(client_name: str, meeting_time: str) -> str:
    """Build a professional HTML email template."""
    return f"""<!DOCTYPE html>
<html dir="rtl" lang="he">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin:0; padding:0; background-color:#f4f4f4; font-family: Arial, sans-serif;">
    <table width="100%" cellpadding="0" cellspacing="0" style="background-color:#f4f4f4; padding:20px;">
        <tr>
            <td align="center">
                <table width="600" cellpadding="0" cellspacing="0" style="background-color:#ffffff; border-radius:8px; overflow:hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.1);">
                    <!-- Header -->
                    <tr>
                        <td style="background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); padding:30px; text-align:center;">
                            <h1 style="color:#ffffff; margin:0; font-size:28px; letter-spacing:1px;">AUTOBOT</h1>
                            <p style="color:#a0a0c0; margin:5px 0 0; font-size:14px;">אוטומציות עסקיות חכמות</p>
                        </td>
                    </tr>
                    <!-- Body -->
                    <tr>
                        <td style="padding:40px 30px;">
                            <h2 style="color:#1a1a2e; margin:0 0 20px; font-size:22px;">הפגישה שלך אושרה! ✓</h2>
                            <p style="color:#333; font-size:16px; line-height:1.6; margin:0 0 15px;">
                                שלום {client_name},
                            </p>
                            <p style="color:#333; font-size:16px; line-height:1.6; margin:0 0 25px;">
                                שמחים לאשר שהפגישה שלך עם אריק נקבעה בהצלחה.
                            </p>
                            <!-- Meeting Details Box -->
                            <table width="100%" cellpadding="0" cellspacing="0" style="background-color:#f8f9fa; border-radius:8px; border-right:4px solid #1a1a2e;">
                                <tr>
                                    <td style="padding:20px 25px;">
                                        <p style="color:#666; font-size:13px; margin:0 0 8px; text-transform:uppercase; letter-spacing:1px;">פרטי הפגישה</p>
                                        <p style="color:#1a1a2e; font-size:18px; font-weight:bold; margin:0 0 8px;">📅 {meeting_time}</p>
                                        <p style="color:#555; font-size:14px; margin:0;">👤 עם: אריק, מייסד AUTOBOT</p>
                                        <p style="color:#555; font-size:14px; margin:5px 0 0;">📍 שיחת טלפון / זום</p>
                                    </td>
                                </tr>
                            </table>
                            <p style="color:#333; font-size:16px; line-height:1.6; margin:25px 0 15px;">
                                בפגישה נדבר על האתגרים שלך ונראה איך אוטומציות יכולות לחסוך לך זמן וכסף.
                            </p>
                            <p style="color:#666; font-size:14px; line-height:1.6; margin:0;">
                                צריך לשנות? פשוט השב למייל הזה או שלח הודעה בוואטסאפ.
                            </p>
                        </td>
                    </tr>
                    <!-- Footer -->
                    <tr>
                        <td style="background-color:#f8f9fa; padding:20px 30px; border-top:1px solid #eee;">
                            <p style="color:#999; font-size:12px; margin:0; text-align:center;">
                                AUTOBOT | אוטומציות עסקיות חכמות<br>
                                <a href="https://autobotil.com" style="color:#1a1a2e; text-decoration:none;">autobotil.com</a>
                            </p>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>"""


def send_confirmation_email(to_email: str, client_name: str, meeting_time: str, start_dt=None, end_dt=None) -> bool:
    """Send a professional confirmation email with optional ICS calendar invite.
    
    Args:
        to_email: Client's email address
        client_name: Client's full name
        meeting_time: Human-readable meeting time string (e.g., "יום שלישי 05.05 בשעה 10:00")
        start_dt: datetime object for meeting start (optional, used for ICS)
        end_dt: datetime object for meeting end (optional, used for ICS)
    """
    try:
        msg = MIMEMultipart("mixed")
        msg["Subject"] = f"אישור פגישה - {meeting_time} | AUTOBOT"
        msg["From"] = f"AUTOBOT <{SMTP_USER}>"
        msg["To"] = to_email
        msg["Reply-To"] = SMTP_USER

        # HTML body
        html_content = _build_html(client_name, meeting_time)
        html_part = MIMEText(html_content, "html", "utf-8")
        
        # Also add plain text fallback
        plain_text = f"""שלום {client_name},

הפגישה שלך עם אריק מ-AUTOBOT אושרה!

מועד: {meeting_time}
עם: אריק, מייסד AUTOBOT
מיקום: שיחת טלפון / זום

צריך לשנות? פשוט השב למייל הזה.

בברכה,
צוות AUTOBOT
autobotil.com"""

        # Create alternative part for HTML + plain text
        alt_part = MIMEMultipart("alternative")
        alt_part.attach(MIMEText(plain_text, "plain", "utf-8"))
        alt_part.attach(html_part)
        msg.attach(alt_part)

        # Attach ICS file if dates provided
        if start_dt and end_dt:
            ics_content = _build_ics(client_name, start_dt, end_dt)
            ics_part = MIMEBase("text", "calendar", method="REQUEST")
            ics_part.set_payload(ics_content.encode("utf-8"))
            encoders.encode_base64(ics_part)
            ics_part.add_header("Content-Disposition", "attachment", filename="meeting.ics")
            msg.attach(ics_part)

        # Send via Titan SMTP
        with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT) as server:
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(SMTP_USER, to_email, msg.as_string())

        print(f"[email_sender] Professional email sent to {to_email} from {SMTP_USER}")
        return True

    except Exception as e:
        print(f"[email_sender] ERROR sending email: {e}")
        return False

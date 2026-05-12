import os
import smtplib
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from urllib.parse import quote


def _build_gcal_url(title: str, start_dt: datetime, description: str = "") -> str:
    """בונה קישור Google Calendar להוספה ידנית (fallback אם ההזמנה לא הגיעה)."""
    end_dt = start_dt + timedelta(hours=1)
    fmt = "%Y%m%dT%H%M%S"
    # Google Calendar מצפה ל-UTC — ישראל UTC+3
    utc_start = (start_dt - timedelta(hours=3)).strftime(fmt) + "Z"
    utc_end = (end_dt - timedelta(hours=3)).strftime(fmt) + "Z"
    params = (
        f"action=TEMPLATE"
        f"&text={quote(title)}"
        f"&dates={utc_start}/{utc_end}"
        f"&details={quote(description)}"
    )
    return f"https://www.google.com/calendar/render?{params}"


def send_confirmation_email(to_email: str, client_name: str, meeting_time: str,
                            start_dt: datetime = None) -> bool:
    gmail_user = os.getenv("GMAIL_USER")
    gmail_password = os.getenv("GMAIL_APP_PASSWORD")
    if not gmail_user or not gmail_password:
        print("Email not configured: missing GMAIL_USER or GMAIL_APP_PASSWORD")
        return False

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"אישור פגישה עם AUTOBOT — {meeting_time}"
        msg["From"] = f"AUTOBOT <{gmail_user}>"
        msg["To"] = to_email

        # טקסט רגיל (fallback)
        plain = f"""שלום {client_name},

הפגישה שלך עם אריק מ-AUTOBOT אושרה!

מועד: {meeting_time}

אם צריך לשנות — פשוט ענה להודעה הזו.

בברכה,
צוות AUTOBOT"""

        # HTML עם כפתור הוסף ליומן
        gcal_url = ""
        if start_dt:
            gcal_url = _build_gcal_url(
                title=f"שיחת ייעוץ עם אריק — AUTOBOT",
                start_dt=start_dt,
                description=f"שיחת ייעוץ אישית עם אריק מ-AUTOBOT\n{meeting_time}"
            )

        if gcal_url:
            add_to_cal_button = f"""
        <div style="text-align:center; margin:30px 0;">
          <a href="{gcal_url}"
             style="background-color:#1a73e8; color:#ffffff; padding:14px 28px;
                    text-decoration:none; border-radius:6px; font-size:16px;
                    font-family:Arial,sans-serif; font-weight:bold; display:inline-block;">
            &#128197; הוסף ליומן Google
          </a>
        </div>"""
        else:
            add_to_cal_button = ""

        html = f"""<!DOCTYPE html>
<html dir="rtl" lang="he">
<head><meta charset="utf-8"></head>
<body style="font-family:Arial,sans-serif; background:#f5f5f5; margin:0; padding:20px;">
  <div style="max-width:500px; margin:auto; background:#ffffff; border-radius:10px;
              padding:30px; box-shadow:0 2px 8px rgba(0,0,0,0.1);">
    <h2 style="color:#1a73e8; margin-top:0;">✅ הפגישה אושרה!</h2>
    <p style="font-size:16px;">שלום <strong>{client_name}</strong>,</p>
    <p style="font-size:16px;">הפגישה שלך עם אריק מ-AUTOBOT אושרה.</p>
    <div style="background:#f0f4ff; border-radius:8px; padding:16px; margin:20px 0;
                border-right:4px solid #1a73e8;">
      <p style="margin:0; font-size:18px; font-weight:bold; color:#333;">
        🗓️ {meeting_time}
      </p>
    </div>
    {add_to_cal_button}
    <p style="font-size:14px; color:#666;">
      קיבלת הזמנה ישירה ליומן — אם לא הגיעה, לחץ על הכפתור למעלה להוסיף ידנית.
    </p>
    <hr style="border:none; border-top:1px solid #eee; margin:20px 0;">
    <p style="font-size:13px; color:#999; margin:0;">
      לשינוי מועד — ענה להודעה הזו.<br>
      צוות AUTOBOT
    </p>
  </div>
</body>
</html>"""

        msg.attach(MIMEText(plain, "plain", "utf-8"))
        msg.attach(MIMEText(html, "html", "utf-8"))

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(gmail_user, gmail_password)
            server.sendmail(gmail_user, to_email, msg.as_string())

        print(f"Confirmation email sent to {to_email}")
        return True
    except Exception as e:
        print(f"Email send error: {e}")
        return False

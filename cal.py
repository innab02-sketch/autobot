import os
import json
import re
from datetime import datetime, timedelta
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

AUTOBOT_CALENDAR_ID = os.getenv("AUTOBOT_CALENDAR_ID")
ARIK_CALENDAR_ID = os.getenv("ARIK_CALENDAR_ID")

SCOPES = ["https://www.googleapis.com/auth/calendar"]

HEBREW_DAYS = {
    "ראשון": 6,
    "שני": 0,
    "שלישי": 1,
    "רביעי": 2,
    "חמישי": 3,
    "שישי": 4,
}


def get_service():
    creds_json = os.getenv("GOOGLE_CREDENTIALS_JSON")
    creds_dict = json.loads(creds_json)
    creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
    return build("calendar", "v3", credentials=creds)


def parse_availability(text: str):
    text = text.strip()
    found_day = None
    for heb, weekday_num in HEBREW_DAYS.items():
        if heb in text:
            found_day = weekday_num
            break

    time_match = re.search(r'(\d{1,2})[:\.](\d{2})', text)
    if not time_match:
        if "בוקר" in text:
            hour, minute = 10, 0
        elif "צהריים" in text:
            hour, minute = 13, 0
        elif "אחה\"צ" in text or "אחרי" in text:
            hour, minute = 15, 0
        elif "ערב" in text:
            hour, minute = 18, 0
        else:
            return None
    else:
        hour = int(time_match.group(1))
        minute = int(time_match.group(2))

    if found_day is None:
        return None

    today = datetime.now()
    days_ahead = found_day - today.weekday()
    if days_ahead <= 0:
        days_ahead += 7

    start_dt = (today + timedelta(days=days_ahead)).replace(
        hour=hour, minute=minute, second=0, microsecond=0
    )
    end_dt = start_dt + timedelta(hours=1)
    return start_dt, end_dt


def is_arik_available(start_dt: datetime, end_dt: datetime) -> bool:
    try:
        service = get_service()
        utc_start = (start_dt - timedelta(hours=3)).isoformat() + "Z"
        utc_end = (end_dt - timedelta(hours=3)).isoformat() + "Z"
        body = {
            "timeMin": utc_start,
            "timeMax": utc_end,
            "items": [{"id": ARIK_CALENDAR_ID}]
        }
        result = service.freebusy().query(body=body).execute()
        busy = result["calendars"][ARIK_CALENDAR_ID]["busy"]
        return len(busy) == 0
    except Exception as e:
        print(f"Freebusy error: {e}")
        return True


def create_event(full_name: str, phone: str, start_dt: datetime, end_dt: datetime) -> bool:
    try:
        service = get_service()
        event = {
            "summary": f"שיחת ייעוץ — {full_name}",
            "description": f"טלפון: {phone}\nנקבע אוטומטית על ידי AUTOBOT",
            "start": {"dateTime": start_dt.isoformat(), "timeZone": "Asia/Jerusalem"},
            "end": {"dateTime": end_dt.isoformat(), "timeZone": "Asia/Jerusalem"},
            "attendees": [{"email": ARIK_CALENDAR_ID}],
            "reminders": {
                "useDefault": False,
                "overrides": [
                    {"method": "email", "minutes": 60},
                    {"method": "popup", "minutes": 15}
                ]
            }
        }
        service.events().insert(
            calendarId=AUTOBOT_CALENDAR_ID,
            body=event,
           sendUpdates="externalOnly"
        ).execute()
        print(f"Meeting created: {full_name} at {start_dt}")
        return True
    except Exception as e:
        print(f"Create event error: {e}")
        return False


def book_meeting(full_name: str, phone: str, availability_str: str) -> bool:
    result = parse_availability(availability_str)
    if not result:
        print(f"Could not parse availability: {availability_str}")
        return False

    start_dt, end_dt = result

    if is_arik_available(start_dt, end_dt):
        return create_event(full_name, phone, start_dt, end_dt)
    else:
        print(f"Arik is busy at {start_dt} — meeting not booked")

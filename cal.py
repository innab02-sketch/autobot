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


def parse_availability(text):
    text = text.strip()
    found_day = None
    for heb, weekday_num in HEBREW_DAYS.items():
        if heb in text:
            found_day = weekday_num
            break

    # Try multiple time formats: 10:00, 10.00, 1000, 10
    time_match = re.search(r'(\d{1,2})[:\.](\d{2})', text)
    if time_match:
        hour = int(time_match.group(1))
        minute = int(time_match.group(2))
    else:
        # Try 4-digit format like 1000 = 10:00, 1400 = 14:00
        four_digit = re.search(r'\b(\d{4})\b', text)
        if four_digit:
            num = four_digit.group(1)
            hour = int(num[:2])
            minute = int(num[2:])
        else:
            # Try standalone 1-2 digit number like "10" = 10:00
            standalone = re.search(r'\b(\d{1,2})\b', text)
            if standalone:
                hour = int(standalone.group(1))
                minute = 0
                # Sanity check - must be a valid hour
                if hour < 7 or hour > 21:
                    hour = None
            else:
                hour = None

            if hour is None:
                if "בוקר" in text:
                    hour, minute = 10, 0
                elif "צהריים" in text:
                    hour, minute = 13, 0
                elif "אחרי" in text:
                    hour, minute = 15, 0
                elif "ערב" in text:
                    hour, minute = 18, 0
                else:
                    return None

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


def is_arik_available(start_dt, end_dt):
    try:
        service = get_service()
        utc_start = (start_dt - timedelta(hours=3)).isoformat() + "Z"
        utc_end = (end_dt - timedelta(hours=3)).isoformat() + "Z"
        items = [{"id": ARIK_CALENDAR_ID}]
        if AUTOBOT_CALENDAR_ID and AUTOBOT_CALENDAR_ID != ARIK_CALENDAR_ID:
            items.append({"id": AUTOBOT_CALENDAR_ID})
        body = {
            "timeMin": utc_start,
            "timeMax": utc_end,
            "items": items
        }
        result = service.freebusy().query(body=body).execute()
        for item in items:
            cal_id = item["id"]
            busy = result["calendars"].get(cal_id, {}).get("busy", [])
            if len(busy) > 0:
                return False
        return True
    except Exception as e:
        print("Freebusy error: " + str(e))
        return True


def create_event(full_name, phone, start_dt, end_dt, client_email=""):
    try:
        service = get_service()
        attendees = []
        if ARIK_CALENDAR_ID and "@" in ARIK_CALENDAR_ID:
            attendees.append({"email": ARIK_CALENDAR_ID})
        if client_email and "@" in client_email:
            attendees.append({"email": client_email})
        event = {
            "summary": "שיחת ייעוץ - " + full_name,
            "description": "טלפון: " + phone + "\nנקבע אוטומטית על ידי AUTOBOT",
            "start": {"dateTime": start_dt.isoformat(), "timeZone": "Asia/Jerusalem"},
            "end": {"dateTime": end_dt.isoformat(), "timeZone": "Asia/Jerusalem"},
            "attendees": attendees,
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
            sendUpdates="all"
        ).execute()
        print("Meeting created: " + full_name + " at " + str(start_dt))
        return True
    except Exception as e:
        print("Create event error: " + str(e))
        return False


def get_available_slots(days_ahead=6):
    try:
        service = get_service()
        today = datetime.now()
        slots = []
        candidate_hours = [9, 10, 11, 14, 15, 16, 17]
        days_checked = 0
        delta = 1
        while days_checked < days_ahead:
            candidate_day = today + timedelta(days=delta)
            delta += 1
            weekday = candidate_day.weekday()
            if weekday == 5:
                continue
            days_checked += 1

            for hour in candidate_hours:
                if weekday == 4 and hour >= 14:
                    continue
                start_dt = candidate_day.replace(hour=hour, minute=0, second=0, microsecond=0)
                end_dt = start_dt + timedelta(hours=1)
                utc_start = (start_dt - timedelta(hours=3)).isoformat() + "Z"
                utc_end = (end_dt - timedelta(hours=3)).isoformat() + "Z"
                items = [{"id": ARIK_CALENDAR_ID}]
                if AUTOBOT_CALENDAR_ID and AUTOBOT_CALENDAR_ID != ARIK_CALENDAR_ID:
                    items.append({"id": AUTOBOT_CALENDAR_ID})
                body = {
                    "timeMin": utc_start,
                    "timeMax": utc_end,
                    "items": items
                }
                result = service.freebusy().query(body=body).execute()
                is_free = all(
                    len(result["calendars"].get(item["id"], {}).get("busy", [])) == 0
                    for item in items
                )
                if is_free:
                    slots.append(start_dt)

        return slots
    except Exception as e:
        print("get_available_slots error: " + str(e))
        return []


def format_slots_for_prompt(slots):
    if not slots:
        return "אין מידע על זמינות כרגע"
    day_names = ["שני", "שלישי", "רביעי", "חמישי", "שישי", "שבת", "ראשון"]
    lines = []
    for s in slots:
        day = day_names[s.weekday()]
        date_str = s.strftime("%d.%m")
        time_str = s.strftime("%H:%M")
        lines.append("יום " + day + " " + date_str + " בשעה " + time_str)
    return "\n".join(lines)


def book_meeting(full_name, phone, availability_str, client_email=""):
    result = parse_availability(availability_str)
    if not result:
        print("Could not parse availability: " + availability_str)
        return False, None

    start_dt, end_dt = result

    if is_arik_available(start_dt, end_dt):
        booked = create_event(full_name, phone, start_dt, end_dt, client_email)
        if booked:
            from sheets import save_reminder
            save_reminder(phone, start_dt)
        return booked, start_dt
    else:
        print("Arik is busy at " + str(start_dt))
        return False, None

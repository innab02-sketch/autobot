import os
import json
from datetime import datetime, timedelta
from google.oauth2 import service_account
from googleapiclient.discovery import build

SCOPES = ['https://www.googleapis.com/auth/calendar']

def _get_calendar_service():
    """יצירת service ל-Google Calendar API"""
    creds_json = os.getenv('GOOGLE_CREDENTIALS_JSON')
    creds_dict = json.loads(creds_json)
    credentials = service_account.Credentials.from_service_account_info(
        creds_dict, scopes=SCOPES
    )
    return build('calendar', 'v3', credentials=credentials)

def check_availability(calendar_id, start_time, end_time):
    """
    בודק אם יש זמן פנוי ביומן
    
    Args:
        calendar_id: ID של היומן (למשל arik@roiescalator.com)
        start_time: datetime של התחלת הפגישה
        end_time: datetime של סוף הפגישה
    
    Returns:
        True אם פנוי, False אם עסוק
    """
    try:
        service = _get_calendar_service()
        
        # בדיקת free/busy
        body = {
            "timeMin": start_time.isoformat() + 'Z',
            "timeMax": end_time.isoformat() + 'Z',
            "items": [{"id": calendar_id}]
        }
        
        result = service.freebusy().query(body=body).execute()
        busy_times = result['calendars'][calendar_id].get('busy', [])
        
        # אם אין אירועים - פנוי
        is_free = len(busy_times) == 0
        
        print(f"Checking {calendar_id} at {start_time}: {'FREE' if is_free else 'BUSY'}")
        return is_free
        
    except Exception as e:
        print(f"check_availability error: {e}")
        return False

def create_meeting(client_name, client_phone, client_email, start_time, duration_minutes=30):
    """
    יוצר פגישה ביומן AUTOBOT ומזמין את אריק
    
    Args:
        client_name: שם הלקוח
        client_phone: טלפון הלקוח
        client_email: מייל הלקוח (אופציונלי)
        start_time: datetime של התחלת הפגישה
        duration_minutes: משך הפגישה בדקות (ברירת מחדל 30)
    
    Returns:
        dict עם פרטי הפגישה או None אם נכשל
    """
    try:
        service = _get_calendar_service()
        autobot_cal = os.getenv('AUTOBOT_CALENDAR_ID')
        arik_email = os.getenv('ARIK_CALENDAR_ID')
        
        end_time = start_time + timedelta(minutes=duration_minutes)
        
        # יצירת אירוע
        event = {
            'summary': f'שיחת ייעוץ - {client_name}',
            'description': f'שיחת ייעוץ עם {client_name}\nטלפון: {client_phone}',
            'start': {
                'dateTime': start_time.isoformat(),
                'timeZone': 'Asia/Jerusalem',
            },
            'end': {
                'dateTime': end_time.isoformat(),
                'timeZone': 'Asia/Jerusalem',
            },
            'attendees': [
                {'email': arik_email, 'responseStatus': 'needsAction'}
            ],
            'reminders': {
                'useDefault': False,
                'overrides': [
                    {'method': 'email', 'minutes': 24 * 60},  # יום לפני
                    {'method': 'popup', 'minutes': 30},       # חצי שעה לפני
                ],
            },
        }
        
        # אם יש מייל ללקוח - נוסיף אותו למשתתפים
        if client_email and '@' in client_email:
            event['attendees'].append({'email': client_email})
        
        # יצירת האירוע
        created_event = service.events().insert(
            calendarId=autobot_cal,
            body=event,
            sendUpdates='all'  # שליחת הזמנות לכולם
        ).execute()
        
        print(f"✅ Meeting created: {created_event.get('htmlLink')}")
        
        return {
            'event_id': created_event['id'],
            'link': created_event.get('htmlLink'),
            'start': start_time,
            'end': end_time
        }
        
    except Exception as e:
        print(f"❌ create_meeting error: {e}")
        return None

def find_available_slots(date, preferred_hours=None):
    """
    מוצא שעות פנויות ביום מסוים
    
    Args:
        date: datetime של היום המבוקש
        preferred_hours: רשימה של שעות מועדפות (למשל [18, 19, 20])
    
    Returns:
        list של datetime פנויים
    """
    if preferred_hours is None:
        preferred_hours = [18, 19, 20]  # ברירת מחדל - ערב
    
    arik_cal = os.getenv('ARIK_CALENDAR_ID')
    available = []
    
    for hour in preferred_hours:
        slot_start = date.replace(hour=hour, minute=0, second=0, microsecond=0)
        slot_end = slot_start + timedelta(minutes=30)
        
        if check_availability(arik_cal, slot_start, slot_end):
            available.append(slot_start)
    
    return available

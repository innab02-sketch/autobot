import os
import json
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials

SHEET_ID = os.getenv("GOOGLE_SHEET_ID")
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

def _get_creds():
    creds_json = os.getenv("GOOGLE_CREDENTIALS_JSON")
    creds_dict = json.loads(creds_json)
    return Credentials.from_service_account_info(creds_dict, scopes=SCOPES)

def _get_client():
    creds = _get_creds()
    return gspread.authorize(creds)

def get_sheet():
    client = _get_client()
    spreadsheet = client.open_by_key(SHEET_ID)
    try:
        return spreadsheet.worksheet("leads")
    except gspread.exceptions.WorksheetNotFound:
        # יצירת דף leads אם לא קיים
        ws = spreadsheet.add_worksheet(title="leads", rows=1000, cols=10)
        ws.update("A1:J1", [["תאריך", "שם מלא", "טלפון", "מייל", "תחום עסק", 
                             "גודל עסק", "אתגר", "ניסיונות קודמים", "זמינות", "סטטוס"]])
        return ws

def _get_reminders_sheet():
    """דף תזכורות"""
    client = _get_client()
    spreadsheet = client.open_by_key(SHEET_ID)
    try:
        return spreadsheet.worksheet("reminders")
    except gspread.exceptions.WorksheetNotFound:
        ws = spreadsheet.add_worksheet(title="reminders", rows=200, cols=3)
        ws.update("A1:C1", [["phone", "meeting_time", "sent"]])
        return ws

def save_lead(save_line):
    """שמירת ליד ב-Google Sheets"""
    try:
        parts = save_line.replace("SAVE|", "").split("|")
        if len(parts) < 7:
            print(f"Invalid SAVE line: {save_line}")
            return False
        
        full_name = parts[0].strip()
        business_type = parts[1].strip()
        business_size = parts[2].strip()
        challenge = parts[3].strip()
        previous_attempts = parts[4].strip()
        availability = parts[5].strip()
        phone = parts[6].strip()
        email = parts[7].strip() if len(parts) > 7 else ""
        
        sheet = get_sheet()
        row = [
            datetime.now().strftime("%Y-%m-%d %H:%M"),
            full_name, phone, email,
            business_type, business_size, challenge,
            previous_attempts, availability, "חדש"
        ]
        
        sheet.append_row(row)
        print(f"✅ Lead saved: {full_name} ({phone})")
        return True
        
    except Exception as e:
        print(f"❌ save_lead error: {e}")
        return False

def save_reminder(phone, meeting_dt):
    """שמירת תזכורת לפגישה"""
    try:
        ws = _get_reminders_sheet()
        meeting_time_str = meeting_dt.strftime("%Y-%m-%d %H:%M")
        ws.append_row([str(phone).strip(), meeting_time_str, "no"])
        print(f"Reminder saved: {phone} at {meeting_time_str}")
    except Exception as e:
        print(f"save_reminder error: {e}")

def get_pending_reminders():
    """קבלת תזכורות ממתינות"""
    try:
        ws = _get_reminders_sheet()
        rows = ws.get_all_values()
        pending = []
        for i, row in enumerate(rows):
            if i == 0:  # skip header
                continue
            if len(row) < 3:
                continue
            phone, meeting_time, sent = row[0], row[1], row[2]
            if sent.strip().lower() in ("yes", "true", "1"):
                continue
            pending.append((i + 1, {"phone": phone, "meeting_time": meeting_time}))
        return pending
    except Exception as e:
        print(f"get_pending_reminders error: {e}")
        return []

def mark_reminder_sent(row_number):
    """סימון תזכורת כנשלחה"""
    try:
        ws = _get_reminders_sheet()
        ws.update_cell(row_number, 3, "yes")
        print(f"Reminder row {row_number} marked as sent")
    except Exception as e:
        print(f"mark_reminder_sent error: {e}")

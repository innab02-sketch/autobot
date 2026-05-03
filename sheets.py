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
    return client.open_by_key(SHEET_ID).sheet1


def _get_reminders_sheet():
    """
    Get or create the 'reminders' worksheet.
    Columns: phone | meeting_time | sent
    """
    client = _get_client()
    spreadsheet = client.open_by_key(SHEET_ID)
    try:
        ws = spreadsheet.worksheet("reminders")
    except gspread.exceptions.WorksheetNotFound:
        ws = spreadsheet.add_worksheet(title="reminders", rows=200, cols=3)
        ws.update("A1:C1", [["phone", "meeting_time", "sent"]])
        print("Created 'reminders' worksheet")
    return ws


def save_lead(save_line: str):
    """
    מקבל שורה בפורמט:
    SAVE|full_name|business_type|business_size|main_challenge|previous_attempts|availability|phone
    """
    try:
        parts = save_line.replace("SAVE|", "").split("|")
        while len(parts) < 7:
            parts.append("-")

        full_name, business_type, business_size, main_challenge, previous_attempts, availability, phone = parts[:7]

        sheet = get_sheet()
        sheet.append_row([
            datetime.now().strftime("%d.%m.%Y"),
            full_name.strip(),
            phone.strip(),
            business_type.strip(),
            main_challenge.strip(),
            previous_attempts.strip(),
            availability.strip(),
            business_size.strip()
        ])
        print(f"Lead saved: {full_name}")
    except Exception as e:
        print(f"Sheets error: {e}")


def save_reminder(phone: str, meeting_dt: datetime):
    """
    Save a reminder row so that check_reminders() can send a 20-minute
    heads-up message before the meeting.

    Called from cal.py after a meeting is successfully booked.
    """
    try:
        ws = _get_reminders_sheet()
        meeting_time_str = meeting_dt.strftime("%Y-%m-%d %H:%M")
        ws.append_row([str(phone).strip(), meeting_time_str, "no"])
        print(f"Reminder saved: {phone} at {meeting_time_str}")
    except Exception as e:
        print(f"save_reminder error: {e}")


def get_pending_reminders():
    """
    Return a list of (row_number, dict) for reminders that have not been
    sent yet.  Each dict has keys: phone, meeting_time.

    Row numbers are 1-indexed (matching gspread conventions) so they can
    be passed directly to mark_reminder_sent().
    """
    try:
        ws = _get_reminders_sheet()
        rows = ws.get_all_values()
        # First row is the header
        pending = []
        for i, row in enumerate(rows):
            if i == 0:
                continue  # skip header
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


def mark_reminder_sent(row_number: int):
    """
    Mark a reminder row as sent by writing "yes" into the 'sent' column
    (column C).  row_number is 1-indexed.
    """
    try:
        ws = _get_reminders_sheet()
        ws.update_cell(row_number, 3, "yes")
        print(f"Reminder row {row_number} marked as sent")
    except Exception as e:
        print(f"mark_reminder_sent error: {e}")
def save_lead(save_line):
    """שמירת ליד ב-Google Sheets"""
    try:
        # פירוש ה-SAVE line
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
        
        # התחברות ל-Sheets
        import os, json
        from google.oauth2 import service_account
        from googleapiclient.discovery import build
        
        creds_json = os.getenv('GOOGLE_CREDENTIALS_JSON')
        creds_dict = json.loads(creds_json)
        credentials = service_account.Credentials.from_service_account_info(
            creds_dict,
            scopes=['https://www.googleapis.com/auth/spreadsheets']
        )
        service = build('sheets', 'v4', credentials=credentials)
        sheet_id = os.getenv('GOOGLE_SHEET_ID')
        
        # הוספת שורה חדשה
        row = [datetime.now().strftime("%Y-%m-%d %H:%M"), full_name, phone, email, 
               business_type, business_size, challenge, previous_attempts, availability, "חדש"]
        
        # ניסיון להוסיף לדף leads
        try:
            service.spreadsheets().values().append(
                spreadsheetId=sheet_id,
                range="leads!A:J",
                valueInputOption="USER_ENTERED",
                body={"values": [row]}
            ).execute()
            print(f"✅ Lead saved: {full_name} ({phone})")
        except:
            # אם דף leads לא קיים, ניצור אותו
            body = {"requests": [{"addSheet": {"properties": {"title": "leads"}}}]}
            service.spreadsheets().batchUpdate(spreadsheetId=sheet_id, body=body).execute()
            service.spreadsheets().values().append(
                spreadsheetId=sheet_id,
                range="leads!A:J",
                valueInputOption="USER_ENTERED",
                body={"values": [row]}
            ).execute()
            print(f"✅ Created leads sheet and saved: {full_name}")
        
        return True
    except Exception as e:
        print(f"❌ save_lead error: {e}")
        return False

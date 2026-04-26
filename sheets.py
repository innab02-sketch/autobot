import os
import json
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials

SHEET_ID = os.getenv("GOOGLE_SHEET_ID")
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


def get_client():
    creds_json = os.getenv("GOOGLE_CREDENTIALS_JSON")
    creds_dict = json.loads(creds_json)
    creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
    return gspread.authorize(creds)


def get_sheet():
    return get_client().open_by_key(SHEET_ID).sheet1


def get_reminders_sheet():
    spreadsheet = get_client().open_by_key(SHEET_ID)
    try:
        return spreadsheet.worksheet("Reminders")
    except Exception:
        sheet = spreadsheet.add_worksheet(title="Reminders", rows=1000, cols=3)
        sheet.append_row(["phone", "meeting_time", "status"])
        return sheet


def save_lead(save_line):
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
        print("Lead saved: " + full_name)
    except Exception as e:
        print("Sheets error: " + str(e))


def save_reminder(phone, meeting_dt):
    try:
        sheet = get_reminders_sheet()
        sheet.append_row([
            str(phone),
            meeting_dt.strftime("%Y-%m-%d %H:%M"),
            "pending"
        ])
        print("Reminder saved for " + str(phone))
    except Exception as e:
        print("Save reminder error: " + str(e))


def get_pending_reminders():
    try:
        sheet = get_reminders_sheet()
        rows = sheet.get_all_records()
        return [(i + 2, r) for i, r in enumerate(rows) if r.get("status") == "pending"]
    except Exception as e:
        print("Get reminders error: " + str(e))
        return []


def mark_reminder_sent(row_num):
    try:
        sheet = get_reminders_sheet()
        sheet.update_cell(row_num, 3, "sent")
    except Exception as e:
        print("Mark reminder error: " + str(e))

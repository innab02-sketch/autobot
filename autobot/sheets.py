import os
import json
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials

SHEET_ID = os.getenv("GOOGLE_SHEET_ID")
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


def get_sheet():
    creds_json = os.getenv("GOOGLE_CREDENTIALS_JSON")
    creds_dict = json.loads(creds_json)
    creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
    client = gspread.authorize(creds)
    return client.open_by_key(SHEET_ID).sheet1


def save_lead(save_line: str):
    """
    מקבל שורה בפורמט:
    SAVE|full_name|business_type|business_size|main_challenge|previous_attempts|availability|phone|email
    """
    try:
        parts = save_line.replace("SAVE|", "").split("|")
        while len(parts) < 8:
            parts.append("-")

        full_name, business_type, business_size, main_challenge, previous_attempts, availability, phone, email = parts[:8]

        sheet = get_sheet()
        sheet.append_row([
            datetime.now().strftime("%d.%m.%Y"),
            full_name.strip(),
            phone.strip(),
            email.strip(),
            business_type.strip(),
            main_challenge.strip(),
            previous_attempts.strip(),
            availability.strip(),
            business_size.strip()
        ])
        print(f"Lead saved: {full_name}")
    except Exception as e:
        print(f"Sheets error: {e}")

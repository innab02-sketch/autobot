import os
import requests

TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_WHATSAPP_FROM = os.getenv("TWILIO_WHATSAPP_FROM", "whatsapp:+14155238886")


def _normalize_phone(phone: str) -> str:
    """Normalize phone number to E.164 format for Twilio.
    
    Handles cases like:
    - "972501234567" -> "+972501234567"
    - "0501234567" -> "+972501234567"  (assumes Israel)
    - "+972501234567" -> "+972501234567"
    - "whatsapp:+972501234567" -> already formatted
    """
    phone = phone.strip()
    
    # Already has whatsapp prefix
    if phone.startswith("whatsapp:"):
        return phone
    
    # Remove any spaces, dashes, parentheses
    phone = phone.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
    
    # If starts with 0, assume Israel country code
    if phone.startswith("0"):
        phone = "972" + phone[1:]
    
    # Ensure starts with +
    if not phone.startswith("+"):
        phone = "+" + phone
    
    return f"whatsapp:{phone}"


def send_message(to: str, text: str):
    if not TWILIO_ACCOUNT_SID or not TWILIO_AUTH_TOKEN:
        print("Twilio credentials missing")
        return None
        
    url = f"https://api.twilio.com/2010-04-01/Accounts/{TWILIO_ACCOUNT_SID}/Messages.json"
    
    to_number = _normalize_phone(to)
    
    print(f"[WhatsApp] Sending to: {to_number} (original: {to})")
    
    payload = {
        "From": TWILIO_WHATSAPP_FROM,
        "To": to_number,
        "Body": text
    }
    
    response = requests.post(
        url,
        auth=(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN),
        data=payload
    )
    
    if not response.ok:
        print(f"[WhatsApp] Send error: {response.status_code} - {response.text}")
    else:
        print(f"[WhatsApp] Message sent OK to {to_number}")
        
    return response

import os
import requests

TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_WHATSAPP_FROM = os.getenv("TWILIO_WHATSAPP_FROM", "whatsapp:+14155238886")

def send_message(to: str, text: str):
    if not TWILIO_ACCOUNT_SID or not TWILIO_AUTH_TOKEN:
        print("Twilio credentials missing")
        return None
        
    url = f"https://api.twilio.com/2010-04-01/Accounts/{TWILIO_ACCOUNT_SID}/Messages.json"
    
    # Ensure the 'to' number has the whatsapp:+ prefix
    to_number = to if to.startswith("whatsapp:") else f"whatsapp:+{to}"
    
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
        print(f"WhatsApp send error: {response.text}")
        
    return response

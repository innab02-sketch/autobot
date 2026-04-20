import os
import requests

WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")
API_URL = f"https://graph.facebook.com/v19.0/{PHONE_NUMBER_ID}/messages"


def send_message(to: str, text: str):
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": text}
    }
    response = requests.post(API_URL, headers=headers, json=payload)
    if not response.ok:
        print(f"WhatsApp send error: {response.text}")
    return response

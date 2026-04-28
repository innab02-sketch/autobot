import os
import requests

SENDPULSE_CLIENT_ID = os.getenv("SENDPULSE_CLIENT_ID")
SENDPULSE_CLIENT_SECRET = os.getenv("SENDPULSE_CLIENT_SECRET")
BOT_ID = "69e09f114ade2ca53a06d540"

def get_token():
    resp = requests.post("https://api.sendpulse.com/oauth/access_token", json={
        "grant_type": "client_credentials",
        "client_id": SENDPULSE_CLIENT_ID,
        "client_secret": SENDPULSE_CLIENT_SECRET
    })
    return resp.json().get("access_token")

def send_message(to: str, text: str):
    token = get_token()
    headers = {"Authorization": f"Bearer {token}"}
    payload = {
        "bot_id": BOT_ID,
        "phone": to,
        "message": {"type": "text", "text": {"body": text}}
    }
    response = requests.post(
        "https://api.sendpulse.com/whatsapp/contacts/sendByPhone",
        headers=headers,
        json=payload
    )
    if not response.ok:
        print(f"WhatsApp send error: {response.text}")
    return response

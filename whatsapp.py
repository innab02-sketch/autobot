import os
import requests

SENDPULSE_CLIENT_ID = os.getenv("sp_id_010553fe80126f67561e764600727f2e")
SENDPULSE_CLIENT_SECRET = os.getenv("sp_sk_dfe6480df3dbdb5b1384e44e15fdef57")
BOT_ID = "69e09f114ade2ca53a06d540"


def get_token():
    resp = requests.post("https://api.sendpulse.com/oauth/access_token", json={
        "grant_type": "client_credentials",
        "client_id": SENDPULSE_CLIENT_ID,
        "client_secret": SENDPULSE_CLIENT_SECRET
    })
    token = resp.json().get("access_token")
    print(f"Token obtained: {bool(token)}")
    return token


def send_message(to: str, text: str):
    token = get_token()
    if not token:
        print("ERROR: Could not get SendPulse token")
        return

    # Ensure phone has + prefix
    phone = to if to.startswith("+") else f"+{to}"

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    payload = {
        "bot_id": BOT_ID,
        "phone": phone,
        "message": {
            "type": "text",
            "text": text
        }
    }
    print(f"Sending to {phone}: {text[:50]}")
    response = requests.post(
        "https://api.sendpulse.com/whatsapp/contacts/sendByPhone",
        headers=headers,
        json=payload
    )
    print(f"SendPulse response: {response.status_code} - {response.text[:200]}")
    return response

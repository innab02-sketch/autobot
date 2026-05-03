import os
import requests

def get_token():
    try:
        # נסיון עם ה-URL הישן
        url = "https://api.sendpulse.com/oauth/access_token"
        payload = {
            "grant_type": "client_credentials",
            "client_id": os.getenv("SENDPULSE_CLIENT_ID"),
            "client_secret": os.getenv("SENDPULSE_CLIENT_SECRET")
        }
        
        print(f"Trying to get token from: {url}")
        resp = requests.post(url, json=payload, timeout=30)
        
        if resp.status_code == 200:
            data = resp.json()
            token = data.get("access_token")
            print(f"✅ Got token: {token[:20]}...")
            return token
        else:
            print(f"❌ Token failed: {resp.status_code} - {resp.text}")
            return None
            
    except Exception as e:
        print(f"❌ Token exception: {e}")
        return None

def send_message(phone, text):
    """Send WhatsApp message via SendPulse API"""
    token = get_token()
    if not token:
        print("No token, cannot send message")
        return False
    
    # SendPulse API endpoint for sending messages
    url = "https://api.sendpulse.com/whatsapp/send"
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "phone": phone,
        "text": text
    }
    
    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=30)
        if resp.status_code == 200:
            print(f"✅ Message sent to {phone}")
            return True
        else:
            print(f"❌ Send failed: {resp.status_code} - {resp.text}")
            return False
    except Exception as e:
        print(f"❌ Send exception: {e}")
        return False

def send_message_by_contact(contact_id, text):
    """Alternative method using contact ID"""
    token = get_token()
    if not token:
        return False
    
    url = "https://api.sendpulse.com/whatsapp/send"
    headers = {"Authorization": f"Bearer {token}"}
    payload = {"contact_id": contact_id, "text": text}
    
    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=30)
        return resp.status_code == 200
    except:
        return False

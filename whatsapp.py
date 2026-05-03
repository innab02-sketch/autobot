import os
from twilio.rest import Client

def send_message(to_phone, message_body):
    """
    שליחת הודעת WhatsApp דרך Twilio
    """
    try:
        account_sid = os.getenv("TWILIO_ACCOUNT_SID")
        auth_token = os.getenv("TWILIO_AUTH_TOKEN")
        from_whatsapp = os.getenv("TWILIO_WHATSAPP_NUMBER")
        
        if not account_sid or not auth_token or not from_whatsapp:
            print("❌ Missing Twilio credentials")
            return False
        
        print(f"📤 Sending message to {to_phone}")
        print(f"   Message: {message_body[:50]}...")
        
        client = Client(account_sid, auth_token)
        
        # וידוא שהמספרים בפורמט הנכון של Twilio
        if not to_phone.startswith("whatsapp:"):
            to_phone = f"whatsapp:{to_phone}"
        if not from_whatsapp.startswith("whatsapp:"):
            from_whatsapp = f"whatsapp:{from_whatsapp}"
        
        message = client.messages.create(
            body=message_body,
            from_=from_whatsapp,
            to=to_phone
        )
        
        print(f"✅ Message sent! SID: {message.sid}")
        return True
        
    except Exception as e:
        print(f"❌ Error sending message: {e}")
        return False

def send_message_by_contact(contact_id, text):
    """פונקציה זהה ל-send_message עבור תאימות"""
    return send_message(contact_id, text)

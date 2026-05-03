import os
import json
import anthropic
import threading
import time
from datetime import datetime, timedelta
from flask import Flask, request, jsonify
from conversation import get_history, add_message, clear_history
from whatsapp import send_message

app = Flask(__name__)

VERIFY_TOKEN = os.getenv("WEBHOOK_VERIFY_TOKEN", "autobot_webhook_2026")
client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

def get_system_prompt():
    return "אתה עוזר וירטואלי של AUTOBOT. אסוף פרטים: שם מלא, טלפון, מייל, תחום עסק, גודל עסק, אתגר, מה ניסו, זמינות לפגישה. בסוף שלח SAVE|שם|עסק|גודל|אתגר|ניסיון|זמינות|טלפון|מייל"

def check_reminders():
    while True:
        try:
            from sheets import get_pending_reminders, mark_reminder_sent
            now = datetime.now()
            reminders = get_pending_reminders()
            for row_num, reminder in reminders:
                meeting_time = datetime.strptime(reminder["meeting_time"], "%Y-%m-%d %H:%M")
                minutes_left = (meeting_time - now).total_seconds() / 60
                if 19 <= minutes_left <= 21:
                    phone = str(reminder["phone"])
                    send_message(phone, "היי! מזכירים שיש לך שיחה בעוד 20 דקות.")
                    mark_reminder_sent(row_num)
        except Exception as e:
            print("Reminder error: " + str(e))
        time.sleep(60)

reminder_thread = threading.Thread(target=check_reminders, daemon=True)
reminder_thread.start()

@app.route("/sendpulse", methods=["POST"])
def handle_sendpulse():
    raw = request.get_json(force=True, silent=True)
    if raw is None:
        return jsonify({"status": "ok"}), 200
    
    events = raw if isinstance(raw, list) else [raw]
    
    for event in events:
        try:
            if event.get("title") != "incoming_message":
                continue
            
            contact = event.get("contact", {})
            phone = contact.get("phone") or contact.get("Phone")
            
            if not phone:
                try:
                    phone = event["info"]["message"]["channel_data"]["message"]["from"]
                except:
                    continue
            
            text = ""
            try:
                text = event["info"]["message"]["channel_data"]["message"]["text"]["body"]
            except:
                text = contact.get("last_message", "")
            
            if not text:
                continue
            
            print(f"Message from {phone}: {text}")
            
            history = get_history(phone)
            history.append({"role": "user", "content": text})
            
            response = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=1024,
                system=get_system_prompt(),
                messages=history
            )
            
            reply = response.content[0].text
            add_message(phone, "user", text)
            add_message(phone, "assistant", reply)
            
            if "SAVE|" in reply:
                save_lines = [l for l in reply.split("\n") if l.startswith("SAVE|")]
                if save_lines:
                    from sheets import save_lead
                    save_lead(save_lines[0])
                    reply = reply.replace(save_lines[0], "").strip()
            
            send_message(phone, reply)
            
        except Exception as e:
            print(f"Error: {e}")
    
    return jsonify({"status": "ok"}), 200

@app.route("/debug-sheets", methods=["GET"])
def debug_sheets():
    import os, json
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    
    result = {}
    sheet_id = os.getenv('GOOGLE_SHEET_ID')
    result['sheet_id'] = sheet_id
    
    try:
        creds_json = os.getenv('GOOGLE_CREDENTIALS_JSON')
        creds_dict = json.loads(creds_json)
        result['json_valid'] = True
        result['client_email'] = creds_dict.get('client_email')
    except Exception as e:
        result['json_valid'] = False
        result['error'] = str(e)
        return result
    
    try:
        credentials = service_account.Credentials.from_service_account_info(
            creds_dict,
            scopes=['https://www.googleapis.com/auth/spreadsheets']
        )
        service = build('sheets', 'v4', credentials=credentials)
        spreadsheet = service.spreadsheets().get(spreadsheetId=sheet_id).execute()
        result['success'] = True
        result['sheet_title'] = spreadsheet['properties']['title']
    except Exception as e:
        result['success'] = False
        result['error'] = str(e)
    
    return result

@app.route("/", methods=["GET"])
def health():
    return "AUTOBOT is running", 200

@app.route("/check-cal")
def check_cal():
    import os
    return {"arik": os.getenv("ARIK_CALENDAR_ID"), "autobot": os.getenv("AUTOBOT_CALENDAR_ID")}

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

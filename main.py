import os
import json
import anthropic
import threading
import time
from datetime import datetime, timedelta
from flask import Flask, request, jsonify
from conversation import get_history, add_message, clear_history
from whatsapp import send_message
from twilio.twiml.messaging_response import MessagingResponse

app = Flask(__name__)

VERIFY_TOKEN = os.getenv("WEBHOOK_VERIFY_TOKEN", "autobot_webhook_2026")
client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

def get_system_prompt():
    return """אתה עוזר וירטואלי של AUTOBOT - מומחה באוטומציות WhatsApp ושירות לקוחות.

תפקידך:
1. לאסוף את הפרטים הבאים מהלקוח בצורה ידידותית ושיחתית:
   - שם מלא
   - טלפון (אם לא ידוע)
   - מייל
   - תחום העסק
   - גודל העסק (כמה עובדים/לקוחות)
   - האתגר העיקרי שמנסים לפתור
   - פתרונות שניסו בעבר
   - זמינות לשיחת ייעוץ

2. כשמגיעים לשאלת הזמינות - שאל: "באיזה יום ושעה נוח לך לשיחת ייעוץ עם אריק?"

3. כשהלקוח מציע יום ושעה - שלח בדיוק בפורמט הזה:
   CHECK_AVAILABILITY|YYYY-MM-DD|HH:MM
   (לדוגמה: CHECK_AVAILABILITY|2026-05-06|18:00)

4. אחרי שתקבל תשובה על הזמינות - שמור את כל הפרטים בפורמט:
   SAVE|שם מלא|תחום עסק|גודל עסק|אתגר|ניסיונות קודמים|זמינות|טלפון|מייל

דוגמה לשיחה:
לקוח: "שלום"
את/ה: "היי! שמחה לעזור 😊 מה השם שלך?"
לקוח: "אני דני"
את/ה: "נעים מאוד דני! מה מספר הטלפון שלך?"
...
לקוח: "אני פנוי ביום שלישי בשעה 18:00"
את/ה: "CHECK_AVAILABILITY|2026-05-06|18:00"
"""

def check_reminders():
    """בדיקת תזכורות כל דקה"""
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
                    send_message(phone, "היי! מזכירים שיש לך שיחה בעוד 20 דקות עם אריק מ-AUTOBOT 📞")
                    mark_reminder_sent(row_num)
        except Exception as e:
            print("Reminder error: " + str(e))
        time.sleep(60)

reminder_thread = threading.Thread(target=check_reminders, daemon=True)
reminder_thread.start()

def process_bot_response(phone, reply):
    """עיבוד תשובת הבוט - טיפול ב-CHECK_AVAILABILITY ו-SAVE"""
    
    # בדיקת זמינות
    if "CHECK_AVAILABILITY|" in reply:
        try:
            from calendar_helper import check_availability, create_meeting, find_available_slots
            from sheets import save_reminder
            
            check_line = [l for l in reply.split("\n") if "CHECK_AVAILABILITY|" in l][0]
            parts = check_line.replace("CHECK_AVAILABILITY|", "").split("|")
            
            if len(parts) >= 2:
                date_str = parts[0].strip()  # YYYY-MM-DD
                time_str = parts[1].strip()  # HH:MM
                
                # המרה ל-datetime
                meeting_dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
                meeting_end = meeting_dt + timedelta(minutes=30)
                
                arik_cal = os.getenv('ARIK_CALENDAR_ID')
                
                # בדיקת זמינות
                from calendar_helper import check_availability
                is_available = check_availability(arik_cal, meeting_dt, meeting_end)
                
                if is_available:
                    # קביעת פגישה
                    history = get_history(phone)
                    client_name = "לקוח"
                    client_email = ""
                    
                    # חיפוש שם ומייל בהיסטוריה
                    for msg in history:
                        if msg['role'] == 'user':
                            if '@' in msg['content']:
                                client_email = msg['content'].strip()
                            elif len(msg['content'].split()) <= 3 and not any(char.isdigit() for char in msg['content']):
                                client_name = msg['content'].strip()
                    
                    from calendar_helper import create_meeting
                    meeting_info = create_meeting(
                        client_name=client_name,
                        client_phone=phone,
                        client_email=client_email,
                        start_time=meeting_dt,
                        duration_minutes=30
                    )
                    
                    if meeting_info:
                        # שמירת תזכורת
                        save_reminder(phone, meeting_dt)
                        
                        # הסרת שורת CHECK והוספת הודעת אישור
                        reply = reply.replace(check_line, "").strip()
                        reply += f"\n\n✅ מעולה! הפגישה נקבעה ליום {meeting_dt.strftime('%d/%m/%Y')} בשעה {meeting_dt.strftime('%H:%M')}.\n"
                        reply += f"אריק יצור איתך קשר בזמן הפגישה 📞\n"
                        reply += f"תקבל תזכורת 20 דקות לפני הפגישה."
                    else:
                        reply = reply.replace(check_line, "").strip()
                        reply += "\n\nמצטער, הייתה בעיה בקביעת הפגישה. אריק יחזור אליך בהקדם."
                else:
                    # אריק עסוק - הצעת שעות חלופיות
                    reply = reply.replace(check_line, "").strip()
                    
                    from calendar_helper import find_available_slots
                    # חיפוש שעות פנויות באותו יום
                    available_slots = find_available_slots(
                        meeting_dt.date(),
                        preferred_hours=[18, 19, 20, 21]
                    )
                    
                    if available_slots:
                        slots_text = ", ".join([s.strftime("%H:%M") for s in available_slots[:3]])
                        reply += f"\n\nאריק עסוק בשעה {time_str} 😕\n"
                        reply += f"האם אחת מהשעות הבאות נוחה לך?\n{slots_text}"
                    else:
                        reply += f"\n\nאריק עסוק ביום {meeting_dt.strftime('%d/%m')} 😕\n"
                        reply += "איזה יום אחר נוח לך לשיחה?"
                        
        except Exception as e:
            print(f"CHECK_AVAILABILITY error: {e}")
            reply = reply.replace(check_line, "").strip()
            reply += "\n\nמצטער, הייתה בעיה בבדיקת הזמינות. אריק יחזור אליך בהקדם."
    
    # שמירת ליד
    if "SAVE|" in reply:
        save_lines = [l for l in reply.split("\n") if l.startswith("SAVE|")]
        if save_lines:
            from sheets import save_lead
            save_lead(save_lines[0])
            reply = reply.replace(save_lines[0], "").strip()
    
    return reply

@app.route("/sendpulse", methods=["POST"])
def handle_sendpulse():
    """תמיכה ב-SendPulse (legacy)"""
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
                model="claude-sonnet-4-20250514",
                max_tokens=1024,
                system=get_system_prompt(),
                messages=history
            )
            
            reply = response.content[0].text
            add_message(phone, "user", text)
            add_message(phone, "assistant", reply)
            
            # עיבוד תשובה
            reply = process_bot_response(phone, reply)
            
            send_message(phone, reply)
            
        except Exception as e:
            print(f"Error: {e}")
    
    return jsonify({"status": "ok"}), 200

@app.route("/twilio-webhook", methods=["POST"])
def handle_twilio():
    """Webhook עבור Twilio WhatsApp"""
    try:
        incoming_msg = request.values.get('Body', '').strip()
        from_number = request.values.get('From', '')
        
        phone = from_number.replace('whatsapp:', '')
        
        if not incoming_msg or not phone:
            return str(MessagingResponse()), 200
        
        print(f"Twilio message from {phone}: {incoming_msg}")
        
        history = get_history(phone)
        history.append({"role": "user", "content": incoming_msg})
        
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            system=get_system_prompt(),
            messages=history
        )
        
        reply = response.content[0].text
        
        add_message(phone, "user", incoming_msg)
        add_message(phone, "assistant", reply)
        
        # עיבוד תשובה (CHECK_AVAILABILITY + SAVE)
        reply = process_bot_response(phone, reply)
        
        resp = MessagingResponse()
        resp.message(reply)
        
        return str(resp), 200
        
    except Exception as e:
        print(f"Twilio webhook error: {e}")
        resp = MessagingResponse()
        resp.message("סליחה, יש לי בעיה טכנית. ננסה שוב בעוד רגע.")
        return str(resp), 200

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
    return "AUTOBOT is running ✅", 200

@app.route("/check-cal")
def check_cal():
    import os
    return {
        "arik": os.getenv("ARIK_CALENDAR_ID"), 
        "autobot": os.getenv("AUTOBOT_CALENDAR_ID")
    }

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

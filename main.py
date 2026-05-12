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

HEBREW_WEEKDAYS = ["שני", "שלישי", "רביעי", "חמישי", "שישי", "שבת", "ראשון"]


def get_system_prompt():
    now = datetime.now()
    date_str = now.strftime("%d.%m.%Y")
    day_name = HEBREW_WEEKDAYS[now.weekday()]

    try:
        from cal import get_available_slots, format_slots_for_prompt
        slots = get_available_slots()
        slots_text = format_slots_for_prompt(slots)
    except Exception as e:
        print("Failed to get calendar slots: " + str(e))
        slots_text = "אין מידע על זמינות כרגע"

    return """אתה מיה — הנציגה הווירטואלית של AUTOBOT, חברה שעוזרת לעסקים לצמוח עם אוטומציות חכמות (WhatsApp, מכירות, שירות לקוחות).
הטון שלך: חם, ישיר, סקרן, לא פורמלי. את מנהלת שיחה כמו בן אדם — לא כמו טופס.
תאריך היום: """ + date_str + ", יום " + day_name + """

## פתיחת שיחה:
כשמישהו פותח איתך שיחה בפעם הראשונה, שלח:
"היי! אני מיה מ-AUTOBOT — במה אפשר לעזור? 😊"

## שפה:
ענה תמיד בשפה של הלקוח.

## המשימה שלך:
לנהל שיחה זורמת, לאסוף מידע על הלקוח, ולתאם לו שיחה עם אריק.

מה לאסוף — בסדר טבעי, לא כמו שאלון:
- שם מלא
- תחום העסק — רשום בדיוק את המילים שהלקוח אמר, ללא שינוי
- גודל העסק (עצמאי / קטן / בינוני / גדול)
- האתגר הכי גדול כרגע
- מה כבר ניסו (אם הזכירו)
- זמינות לשיחה
- טלפון
- מייל — שאל לקראת הסוף: "ומה המייל שלך? אשלח לך אישור"

## איך לנהל את השיחה:
- שאלה אחת בכל הודעה, לא יותר
- לפני כל שאלה — תגובה קצרה וחמה למה שנאמר
- בדוק את היסטוריית השיחה — אל תשאל דברים שכבר ענו עליהם
- אל תציע פתרונות טכניים — אריק יעשה את זה בשיחה
- מקסימום 1-2 אימוג'ים בהודעה

## תיאום פגישה:
שאל "מתי נוח לך — בוקר, צהריים או ערב?"
לאחר שענו — הצע 2-3 שעות מהרשימה הבאה בלבד:

""" + slots_text + """

אם הלקוח מציע שעה שלא ברשימה — הצע את הקרובות מהרשימה. אל תאשר מועד שאינו ברשימה.

## סיכום לפני סגירה:
אחרי שאספת את כל המידע — סכם ובקש אישור:
"רק לוודא שהבנתי נכון —
שם: [בדיוק]
עסק: [בדיוק]
האתגר: [בדיוק]
מה ניסית: [בדיוק / 'לא ציינת']
זה נכון? יש עוד משהו שחשוב שאריק ידע?"

חשוב: העתק את המילים של הלקוח כפי שאמר — אל תפרש, אל תתרגם, אל תשנה.

## אחרי אישור הסיכום:
"נשמע בדיוק כמו משהו שאנחנו עושים. אריק יוכל לתת לך תמונה מדויקת יותר בשיחה קצרה."

## סיום שיחה:
"מעולה [שם]! קבענו עם אריק ל[יום ותאריך מדויקים] בשעה [שעה מדויקת]. בינתיים אם עולה משהו — אני פה 👍"
תמיד ציין שעה מדויקת — לא "בשעות הפעילות" או כל ניסוח מעורפל.
אל תאמר ששלחת מייל או הודעה — המערכת שולחת אוטומטית אחרי SAVE.

## שמירת נתונים:
אחרי שהלקוח אישר את הסיכום, ההודעה האחרונה חייבת להסתיים בשורה:
SAVE|[full_name]|[business_type]|[business_size]|[main_challenge]|[previous_attempts]|[availability]|[phone]|[email]
רשום בדיוק מה שהלקוח אמר.
לדוגמה:
SAVE|ישראל ישראלי|נדלן|קטן|אין מספיק לידים|פרסום בפייסבוק|רביעי 14:00|0521234567|israel@gmail.com"""


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
                    send_message(phone, "היי! רק מזכיר/ת שיש לך שיחה עם אריק בעוד 20 דקות. מחכים לך!")
                    mark_reminder_sent(row_num)
        except Exception as e:
            print("Reminder check error: " + str(e))
        time.sleep(60)


reminder_thread = threading.Thread(target=check_reminders, daemon=True)
reminder_thread.start()


@app.route("/admin/clear/<phone>", methods=["GET"])
def admin_clear(phone):
    token = request.args.get("token", "")
    if token != VERIFY_TOKEN:
        return "Forbidden", 403
    clear_history(phone)
    return "History cleared for " + phone, 200


@app.route("/admin/test-email", methods=["GET"])
def test_email():
    token = request.args.get("token", "")
    if token != VERIFY_TOKEN:
        return "Forbidden", 403
    to = request.args.get("to", "")
    if not to:
        return "Missing ?to=email", 400
    gmail_user = os.getenv("GMAIL_USER", "")
    gmail_pass = os.getenv("GMAIL_APP_PASSWORD", "")
    if not gmail_user or not gmail_pass:
        return f"Missing env vars: GMAIL_USER={'set' if gmail_user else 'MISSING'}, GMAIL_APP_PASSWORD={'set' if gmail_pass else 'MISSING'}", 200
    from email_sender import send_confirmation_email
    ok = send_confirmation_email(to, "בדיקה", "יום שלישי 29.04 בשעה 10:00")
    return ("Email sent OK" if ok else "Email FAILED — check logs"), 200


@app.route("/webhook", methods=["GET"])
def verify_webhook():
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")
    if mode == "subscribe" and token == VERIFY_TOKEN:
        return challenge, 200
    return "Forbidden", 403


def book_calendar(phone, save_line):
    try:
        parts = save_line.replace("SAVE|", "").split("|")
        if len(parts) < 7:
            return
        full_name = parts[0].strip()
        availability = parts[5].strip()
        client_phone = parts[6].strip()
        client_email = parts[7].strip() if len(parts) > 7 else ""
        from cal import book_meeting
        booked, start_dt = book_meeting(full_name, client_phone, availability, client_email)
        if booked and start_dt:
            day_names = ["שני", "שלישי", "רביעי", "חמישי", "שישי", "שבת", "ראשון"]
            day = day_names[start_dt.weekday()]
            time_str = start_dt.strftime("%H:%M")
            date_str = start_dt.strftime("%d.%m")
            meeting_time_str = "יום " + day + " " + date_str + " בשעה " + time_str
            send_message(phone, "הפגישה נקבעה! " + meeting_time_str + " - אריק יחכה לך 👍")
            # שמירת תזכורת ל-20 דקות לפני
            try:
                from sheets import save_reminder
                save_reminder(phone, start_dt)
            except Exception as re:
                print("save_reminder error: " + str(re))
            # שליחת מייל אישור עם כפתור "הוסף ליומן"
            if client_email and "@" in client_email:
                from email_sender import send_confirmation_email
                send_confirmation_email(client_email, full_name, meeting_time_str, start_dt)
    except Exception as e:
        print("Calendar booking error: " + str(e))


def process_message(phone, text):
    """
    Core message processing logic shared by both /webhook and /sendpulse routes.
    Takes a phone number and message text, processes through Claude AI,
    handles SAVE| lines for lead saving and calendar booking, and sends reply.
    """
    if not text:
        return

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
        save_lines = [line for line in reply.split("\n") if line.startswith("SAVE|")]
        if save_lines:
            save_line = save_lines[0]
            from sheets import save_lead
            save_lead(save_line)
            book_calendar(phone, save_line)
            visible_reply = reply.replace(save_line, "").strip()
            send_message(phone, visible_reply)
    else:
        send_message(phone, reply)


@app.route("/webhook", methods=["POST"])
def handle_webhook():
    data = request.get_json()
    try:
        entry = data["entry"][0]
        changes = entry["changes"][0]
        value = changes["value"]

        if "messages" not in value:
            return jsonify({"status": "ok"}), 200

        message = value["messages"][0]
        phone = message["from"]
        text = message.get("text", {}).get("body", "")

        process_message(phone, text)

    except Exception as e:
        print("Webhook error: " + str(e))

    return jsonify({"status": "ok"}), 200


# ---------------------------------------------------------------------------
# SendPulse webhook endpoint
# ---------------------------------------------------------------------------
# SendPulse sends incoming-message webhooks as a JSON **array** of event
# objects.  Each object has the structure documented at
# https://sendpulse.com/integrations/api/chatbot/webhooks
#
# Phone number extraction priority:
#   1. contact.phone          (top-level field present in some payloads)
#   2. contact.variables.Phone / contact.variables.phone
#   3. info.message.channel_data.message.from  (WhatsApp sender ID)
#
# Message text extraction priority:
#   1. info.message.channel_data.message.text.body
#   2. contact.last_message
# ---------------------------------------------------------------------------

@app.route("/twilio", methods=["POST"])
def handle_twilio():
    try:
        # Twilio sends data as form-urlencoded
        from_number = request.form.get("From", "")
        body = request.form.get("Body", "")
        
        if not from_number or not body:
            return "Missing From or Body", 400
            
        # Extract phone number (strip "whatsapp:+" prefix)
        if from_number.startswith("whatsapp:+"):
            phone = from_number[10:]
        elif from_number.startswith("whatsapp:"):
            phone = from_number[9:]
        elif from_number.startswith("+"):
            phone = from_number[1:]
        else:
            phone = from_number
            
        print(f"Twilio incoming: phone={phone}, text={body[:80]}")
        process_message(phone, body)
        
        # Return empty TwiML response
        return "<Response></Response>", 200, {'Content-Type': 'text/xml'}
        
    except Exception as e:
        print("Twilio webhook error: " + str(e))
        import traceback
        traceback.print_exc()
        return "Error", 500

@app.route("/sendpulse", methods=["POST"])
def handle_sendpulse():
    raw = request.get_json(force=True, silent=True)
    if raw is None:
        print("SendPulse: empty or invalid JSON body")
        return jsonify({"status": "ok"}), 200

    # SendPulse may send a single object or an array of objects
    events = raw if isinstance(raw, list) else [raw]

    for event in events:
        try:
            title = event.get("title", "")
            service = event.get("service", "")

            # Only process incoming WhatsApp messages
            if title != "incoming_message":
                print(f"SendPulse: skipping event title={title}")
                continue

            # --- Extract phone number ---
            contact = event.get("contact", {})
            phone = contact.get("phone") or contact.get("Phone")

            if not phone:
                variables = contact.get("variables", {})
                phone = variables.get("Phone") or variables.get("phone")

            if not phone:
                # Fallback: use the "from" field in channel_data (WhatsApp sender)
                try:
                    from_id = event["info"]["message"]["channel_data"]["message"]["from"]
                    phone = str(from_id)
                except (KeyError, TypeError):
                    pass

            if not phone:
                print("SendPulse: could not extract phone number")
                print("SendPulse: full event: " + json.dumps(event, ensure_ascii=False, default=str)[:2000])
                continue

            # Normalize phone: ensure it's a string, strip whitespace
            phone = str(phone).strip()

            # --- Extract message text ---
            text = ""
            try:
                text = event["info"]["message"]["channel_data"]["message"]["text"]["body"]
            except (KeyError, TypeError):
                pass

            if not text:
                text = contact.get("last_message", "")

            if not text:
                print(f"SendPulse: empty message from {phone}, skipping")
                continue

            print(f"SendPulse incoming: phone={phone}, text={text[:80]}")
            process_message(phone, text)

        except Exception as e:
            print("SendPulse event error: " + str(e))
            import traceback
            traceback.print_exc()

    return jsonify({"status": "ok"}), 200


@app.route("/", methods=["GET"])
def health():
    return "AUTOBOT is running", 200


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

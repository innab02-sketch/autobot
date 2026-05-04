import os
import json
import anthropic
import threading
import time
import traceback
from datetime import datetime, timedelta
from flask import Flask, request, jsonify
from conversation import get_history, add_message, clear_history
from whatsapp import send_message

app = Flask(__name__)

from voice import voice_bp
app.register_blueprint(voice_bp)

VERIFY_TOKEN = os.getenv("WEBHOOK_VERIFY_TOKEN", "autobot_webhook_2026")
client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

HEBREW_WEEKDAYS = ["שני", "שלישי", "רביעי", "חמישי", "שישי", "שבת", "ראשון"]

# Per-phone lock to prevent concurrent message processing
_phone_locks = {}
_locks_lock = threading.Lock()

def _get_phone_lock(phone):
    with _locks_lock:
        if phone not in _phone_locks:
            _phone_locks[phone] = threading.Lock()
        return _phone_locks[phone]


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

    return "תאריך היום: " + date_str + ", יום " + day_name + """

## מי אתה
אתה הבוט של AUTOBOT — חברה שעוזרת לעסקים לבנות אוטומציות (WhatsApp, תהליכי מכירה, שירות לקוחות, אינטגרציות).
אתה השלב הראשון — מנהל שיחה קצרה וטבעית, מבין מה הלקוח צריך, ומתאם שיחת ייעוץ עם אריק.

## איך אתה מדבר
- אתה לא רובוט ולא טופס. אתה מדבר כמו בן אדם נורמלי בוואטסאפ — קצר, ישיר, חם.
- אל תחזור על דברים שכבר אמרת. אל תשתמש בניסוחים חוזרים כמו "מעולה!" או "נשמע מצוין!" בכל הודעה — תגוון.
- אל תסכם מחדש מידע שהלקוח כבר נתן באמצע השיחה. סיכום — רק פעם אחת, בסוף.
- שאלה אחת בכל הודעה. לא יותר.
- מקסימום אימוג'י אחד בהודעה, ורק כשזה טבעי. לא חובה.
- תגובה קצרה ואמפתית לפני שאלה הבאה — אבל לא תמיד אותו משפט.
- אם הלקוח כותב בעברית — ענה בעברית. אם באנגלית — באנגלית. תמיד בשפת הלקוח.

## פתיחת שיחה
כשמישהו פותח שיחה בפעם הראשונה:
"היי! אני הבוט של AUTOBOT 🤖 במה אפשר לעזור?"

## מה צריך לאסוף (בסדר גמיש, בזרימה טבעית)
1. שם מלא
2. תחום העסק — בדיוק כמו שהלקוח אומר. אם אמר "חנות אוזניות אונליין" זה מה שנשמר. לא "מסחר אלקטרוני", לא שום פרשנות.
3. גודל העסק — עצמאי / קטן / בינוני / גדול
4. האתגר או הכאב המרכזי
5. מה כבר ניסו (אם רלוונטי — אם לא עלה בשיחה, אפשר לשאול "ניסית כבר משהו בנושא?")
6. זמינות — ראה הנחיות למטה
7. מספר טלפון
8. מייל — שאל בסוף: "מה המייל שלך? ככה נשלח לך אישור על הפגישה"

## שעות פנויות אצל אריק (מעודכן מהקלנדר — רק אלה):
""" + slots_text + """

## תיאום זמינות — ככה עושים את זה:
1. שאל: "מתי יותר נוח לך — בוקר, צהריים או ערב?"
2. אחרי שענה — הצע 2-3 אפשרויות מהרשימה למעלה שמתאימות. כתוב אותן עם יום ותאריך ושעה, למשל: "יש לי פנוי יום שלישי 29.04 ב-10:00 או רביעי 30.04 ב-14:00 — מה עדיף?"
3. אחרי שבחר — אשר ותמשיך הלאה.
4. אם הלקוח מבקש מועד שלא ברשימה — אל תאשר. הצע 2-3 חלופות מהרשימה.
⛔ אסור לאשר שעה שלא מופיעה ברשימה למעלה.

## דברים שאסור לעשות — בשום מצב:
- אסור לשנות את הניסוח של הלקוח. מה שאמר = מה שנשמר.
- אסור לטעון ששלחת מייל, אישור, או כל דבר שלא באמת נשלח. המערכת שולחת אוטומטית אחרי ה-SAVE.
- אסור לכתוב "בשעות הפעילות" — תמיד ציין יום ושעה מדויקים.
- אסור להציע פתרונות טכניים — זה התפקיד של אריק בשיחה.

## סיכום — פעם אחת, בסוף, לפני סגירה
אחרי שאספת הכל, תסכם ותבקש אישור:
"רגע, רק לוודא שהכל נכון —
שם: [מה שאמר]
עסק: [מה שאמר]
אתגר: [מה שאמר]
מה ניסית: [מה שאמר, או 'לא ציינת']
הכל מדויק?"

⛔ חוק ברזל: העתק בדיוק את המילים של הלקוח. לא לתרגם, לא לפרש, לא לסכם אחרת.

## אחרי שאישר את הסיכום
אם הצורך ברור: "נשמע בדיוק כמו משהו שאנחנו עושים. אריק יוכל לפרט בשיחה."
אם לא ברור: "נשמע מעניין — שיחה קצרה עם אריק תבהיר את התמונה."

## סיום השיחה
השתמש ביום ובשעה שסוכמו:
"מעולה [שם]! הפגישה עם אריק ביום [יום ותאריך] בשעה [שעה]. אם יעלו שאלות עד אז — אני פה 👍"

## שמירת נתונים — קריטי
אחרי שהלקוח אישר הכל, ההודעה האחרונה שלך חייבת להסתיים בשורה הזו (בשורה נפרדת):
SAVE|[full_name]|[business_type]|[business_size]|[main_challenge]|[previous_attempts]|[availability]|[phone]|[email]

⛔ חשוב מאוד — שדה ה-availability חייב להיות בפורמט פשוט: "יום_בשבוע שעה" בלבד.
✅ נכון: רביעי 14:00
✅ נכון: שלישי 10:00
❌ לא: יום רביעי 07.05 ב-14:00
❌ לא: רביעי 07.05 14:00
❌ לא: ב-14:00 ביום רביעי

כלומר — בשדה availability בשורת SAVE, כתוב רק את שם היום ואת השעה. בלי תאריך, בלי "יום", בלי "ב-".

דוגמה מלאה:
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


@app.route("/admin/test-booking", methods=["GET"])
def test_booking():
    token = request.args.get("token", "")
    if token != VERIFY_TOKEN:
        return "Forbidden", 403
    availability = request.args.get("avail", "שלישי 10:00")
    name = request.args.get("name", "Test User")
    email = request.args.get("email", "")
    try:
        from cal import parse_availability, is_arik_available, book_meeting
        result = parse_availability(availability)
        if not result:
            return f"parse_availability FAILED for: {availability}", 200
        start_dt, end_dt = result
        available = is_arik_available(start_dt, end_dt)
        return f"Parsed: {start_dt} - {end_dt}\nArik available: {available}\nWould book: {name} at {start_dt}", 200
    except Exception as e:
        import traceback
        return f"ERROR: {e}\n{traceback.format_exc()}", 200


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
        print(f"[book_calendar] phone={phone}, parts={parts}")

        if len(parts) < 7:
            print(f"[book_calendar] ERROR: not enough fields ({len(parts)}), need at least 7. save_line={save_line}")
            return

        full_name = parts[0].strip()
        availability = parts[5].strip()
        client_phone = parts[6].strip()
        client_email = parts[7].strip() if len(parts) > 7 else ""

        print(f"[book_calendar] name={full_name}, availability='{availability}', phone={client_phone}, email={client_email}")

        from cal import book_meeting
        booked, start_dt = book_meeting(full_name, client_phone, availability, client_email)

        print(f"[book_calendar] book_meeting returned: booked={booked}, start_dt={start_dt}")

        if booked and start_dt:
            day_names = ["שני", "שלישי", "רביעי", "חמישי", "שישי", "שבת", "ראשון"]
            day = day_names[start_dt.weekday()]
            time_str = start_dt.strftime("%H:%M")
            date_str = start_dt.strftime("%d.%m")
            meeting_time_str = "יום " + day + " " + date_str + " בשעה " + time_str
            send_message(phone, "הפגישה נקבעה! " + meeting_time_str + " - אריק יחכה לך 👍")
            if client_email and "@" in client_email:
                from email_sender import send_confirmation_email
                email_ok = send_confirmation_email(client_email, full_name, meeting_time_str)
                print(f"[book_calendar] confirmation email to {client_email}: {'OK' if email_ok else 'FAILED'}")
            else:
                print(f"[book_calendar] no valid email, skipping confirmation. client_email='{client_email}'")
        else:
            print(f"[book_calendar] booking failed or no start_dt. booked={booked}, start_dt={start_dt}")
    except Exception as e:
        print(f"[book_calendar] EXCEPTION: {e}")
        traceback.print_exc()


def process_message(phone, text):
    """
    Core message processing logic shared by both /webhook and /sendpulse routes.
    Takes a phone number and message text, processes through Claude AI,
    handles SAVE| lines for lead saving and calendar booking, and sends reply.
    """
    if not text:
        return

    lock = _get_phone_lock(phone)
    if not lock.acquire(timeout=30):
        print(f"Skipping message from {phone} - still processing previous message")
        return

    try:
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
    finally:
        lock.release()


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
            return "<Response></Response>", 200, {'Content-Type': 'text/xml'}
        
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
            traceback.print_exc()

    return jsonify({"status": "ok"}), 200


@app.route("/", methods=["GET"])
def health():
    return "AUTOBOT is running", 200


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

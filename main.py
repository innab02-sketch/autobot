import os
import json
import anthropic
import threading
import time
from datetime import datetime, timedelta
from flask import Flask, request, jsonify
from conversation import get_history, add_message, clear_history
from whatsapp import send_message, send_message_by_contact

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

    return "תאריך היום: " + date_str + ", יום " + day_name + """

## ⛔️ אסורים מוחלטים — עבירה על אחד מהם היא שגיאה קריטית:
1. אסור לשנות את ניסוח העסק של הלקוח — לא לתרגם, לא לפרש, לא לסכם. "חנות אוזניות אונליין" = "חנות אוזניות אונליין". לא "מסחר אלקטרוני", לא שום דבר אחר.
2. אסור לטעון ששלחת מייל, הודעה, אישור, או כל דבר אחר שלא נשלח בפועל — רק לאחר קבלת המייל ורישום SAVE המערכת שולחת אישור אוטומטית.
3. בסיום השיחה — חייב לציין את היום והשעה המדויקים שסוכמו. אסור לכתוב "בשעות הפעילות" או כל ניסוח מעורפל אחר.
4. אסור להציע שעה שאינה ברשימת השעות הפנויות למטה.

## זהות:
אתה עוזר וירטואלי של AUTOBOT - חברה שמתמחה באוטומציות עסקיות (WhatsApp, תהליכי מכירה, שירות לקוחות, ואינטגרציות).

## פתיחת שיחה:
כשלקוח פותח שיחה בפעם הראשונה, שלח:
"היי! אני הבוט של AUTOBOT פה במה אפשר לעזור?"

## שפה:
ענה תמיד בשפה שבה הלקוח פתח את השיחה.

## תפקיד:
אתה השלב הראשון במסע הלקוח. תפקידך לנהל שיחה אנושית וזורמת, לאסוף תמונת מצב מלאה, ולהעביר ליד איכותי לאריק.

## שעות פנויות אצל אריק (מהקלנדר, מעודכן — אלה בלבד):
""" + slots_text + """

## מידע לאיסוף (חובה בסדר גמיש):
1. שם מלא
2. תחום העסק (כפי שהלקוח מגדיר — מילה במילה)
3. גודל העסק (עצמאי/קטן/בינוני/גדול)
4. האתגר/כאב המרכזי
5. מה כבר ניסו לפתור את הבעיה (אם רלוונטי)
6. זמינות לשיחת ייעוץ — ראה הנחיות "שאלת זמינות" למטה
7. מספר טלפון
8. כתובת מייל — שאל בסוף: "ומה המייל שלך? נשלח לך אישור פגישה"

## שאלת זמינות — חובה לפי הסדר:
1. שאל "מתי נוח לך? בוקר/צהריים/ערב?"
2. לאחר שהלקוח ענה — הצע 2-3 אפשרויות פנויות מהרשימה למעלה בלבד שמתאימות למה שאמר
   דוגמה: "מעולה! יש לי פנוי ביום שלישי 29.04 ב-10:00 או ביום רביעי 30.04 ב-14:00 — מה מתאים?"
3. לאחר שהלקוח בחר שעה מהרשימה — אשר את הבחירה ועבור לשאלה הבאה
4. אם הלקוח מציע מועד שאינו ברשימה — הצע את 2-3 האפשרויות הקרובות ביותר מהרשימה. אסור לאשר מועד שלא ברשימה.

## כללי ברזל — חובה לקיים:
- שאלה אחת בלבד בכל הודעה
- אסור לשאול על מידע שכבר ניתן — לפני כל שאלה בדוק את היסטוריית השיחה
- תגובה אמפתית קצרה לפני שאלה הבאה
- טון ישיר וחברי - לא פורמלי
- אל תציע פתרונות טכניים
- מקסימום 1-2 אימוגי'ים למסר

## שלב הסיכום:
לאחר שאספת את כל המידע הנדרש, חובה לסכם ולבקש אישור לפני שממשיכים לתיאום.

חוק ברזל לסיכום: העתק בדיוק את המילים שהלקוח אמר — אל תפרש, אל תשנה, אל תתרגם, אל תמציא.
לדוגמה: אם הלקוח אמר "חנות אוזניות אונליין" — כתוב "חנות אוזניות אונליין" ולא "מסחר אלקטרוני" או כל ניסוח אחר.

פורמט הסיכום:
"רק לוודא שהבנתי נכון -
שם: [מה שאמר בדיוק]
עסק: [מה שאמר בדיוק]
האתגר: [מה שאמר בדיוק]
מה ניסית: [מה שאמר בדיוק, או 'לא ציינת']
זה נכון? יש עוד משהו שחשוב שאריק ידע?"

## לאחר אישור הסיכום:
אם הצורך ברור: "נשמע בדיוק כמו משהו שאנחנו עושים. אריק יוכל לתת לך תמונה מדויקת יותר בשיחה קצרה."
אם לא ברור: "זה נשמע מעניין אבל צריך עוד בירור - בדיוק בשביל זה שיחה עם אריק תועיל."

## סיום שיחה — חובה:
השתמש בדיוק ביום ובשעה שסוכמו בשיחה:
"מעולה [שם]! קבענו את הפגישה עם אריק ל[יום ותאריך מדויקים שסוכמו] בשעה [שעה מדויקת שסוכמה]. בינתיים אם עולות שאלות - אני פה 👍"
אסור לכתוב "בשעות הפעילות" — תמיד ציין את השעה המדויקת שהלקוח בחר.

## שמירת נתונים - חובה:
לאחר שהלקוח אישר את הסיכום, ההודעה האחרונה שלך חייבת להסתיים בשורה:
SAVE|[full_name]|[business_type]|[business_size]|[main_challenge]|[previous_attempts]|[availability]|[phone]|[email]

השתמש בדיוק במה שהלקוח אמר — אל תשנה, אל תתרגם, אל תסכם אחרת.לדוגמה:
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
            if client_email and "@" in client_email:
                from email_sender import send_confirmation_email
                send_confirmation_email(client_email, full_name, meeting_time_str)
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

@app.route('/debug-sheets', methods=['GET'])
def debug_sheets():
    """בדיקת גישה ל-Google Sheets"""
    import os, json
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    
    result = {}
    
    # 1. בדיקת SHEET_ID
    sheet_id = os.getenv('GOOGLE_SHEET_ID')
    result['sheet_id'] = sheet_id
    
    # 2. בדיקת JSON credentials
    try:
        creds_json = os.getenv('GOOGLE_CREDENTIALS_JSON')
        creds_dict = json.loads(creds_json)
        result['json_valid'] = True
        result['client_email'] = creds_dict.get('client_email')
        result['project_id'] = creds_dict.get('project_id')
    except Exception as e:
        result['json_valid'] = False
        result['json_error'] = str(e)
        return result
    
    # 3. ניסיון גישה ל-Sheet
    try:
        credentials = service_account.Credentials.from_service_account_info(
            creds_dict,
            scopes=['https://www.googleapis.com/auth/spreadsheets']
        )
        service = build('sheets', 'v4', credentials=credentials)
        spreadsheet = service.spreadsheets().get(spreadsheetId=sheet_id).execute()
        result['success'] = True
        result['sheet_title'] = spreadsheet['properties']['title']
        result['sheet_url'] = f"https://docs.google.com/spreadsheets/d/{sheet_id}/edit"
    except Exception as e:
        result['success'] = False
        result['error'] = str(e)
        if hasattr(e, 'status_code'):
            result['status_code'] = e.status_code
@app.route('/debug-check')
def debug_check():
    import os
    return {
        "arik": os.getenv("ARIK_CALENDAR_ID"),
        "autobot": os.getenv("AUTOBOT_CALENDAR_ID")
    }
    def process_message(phone, text):
    print(f"\n=== PROCESSING MESSAGE from {phone} ===")
    print(f"Text: {text[:200]}")
    
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
if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

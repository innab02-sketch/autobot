import os
import json
import anthropic
from datetime import datetime
from flask import Flask, request, jsonify
from conversation import get_history, add_message, clear_history
from whatsapp import send_message, send_message_by_contact

app = Flask(__name__)

from voice import voice_bp
app.register_blueprint(voice_bp)

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
    except Exception:
        slots_text = "אין מידע על זמינות כרגע"

    return """תאריך היום: """ + date_str + """, יום """ + day_name + """

## ⛔ אסורים מוחלטים — עבירה על אחד מהם היא שגיאה קריטית:
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
2. לאחר שהלקוח ענה — הצע 2-3 אפשרויות פנויות **מהרשימה למעלה בלבד** שמתאימות למה שאמר
   דוגמה: "מעולה! יש לי פנוי ביום שלישי 29.04 ב-10:00 או ביום רביעי 30.04 ב-14:00 — מה מתאים?"
3. לאחר שהלקוח בחר שעה מהרשימה — אשר את הבחירה ועבור לשאלה הבאה
4. **אם הלקוח מציע מועד שאינו ברשימה — חובה לענות: "אבדוק עם אריק ואחזור אליך בהקדם" — אסור לאשר מועד שלא ברשימה**

## כללי ברזל — חובה לקיים:
- שאלה אחת בלבד בכל הודעה
- **אסור לשאול על מידע שכבר ניתן** — לפני כל שאלה בדוק את היסטוריית השיחה
- תגובה אמפתית קצרה לפני שאלה הבאה
- טון ישיר וחברי - לא פורמלי
- אל תציע פתרונות טכניים
- מקסימום 1-2 אימוגי'ים למסר
- **אסור לטעון ששלחת מייל, הודעה, או כל דבר אחר שלא שלחת בפועל**

## שלב הסיכום:
לאחר שאספת את כל המידע הנדרש, **חובה** לסכם ולבקש אישור לפני שממשיכים לתיאום.

**חוק ברזל לסיכום: העתק בדיוק את המילים שהלקוח אמר — אל תפרש, אל תשנה, אל תתרגם, אל תמציא.**
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
**אסור לכתוב "בשעות הפעילות" — תמיד ציין את השעה המדויקת שהלקוח בחר.**

## שמירת נתונים - חובה:
לאחר שהלקוח אישר את הסיכום, ההודעה האחרונה שלך חייבת להסתיים בשורה:
SAVE|[full_name]|[business_type]|[business_size]|[main_challenge]|[previous_attempts]|[availability]|[phone]|[email]

השתמש בדיוק במה שהלקוח אמר — אל תשנה, אל תתרגם, אל תסכם אחרת.

לדוגמה:
SAVE|ישראל ישראלי|נדלן|קטן|אין מספיק לידים|פרסום בפייסבוק|רביעי 14:00|0521234567|israel@gmail.com"""


@app.route("/webhook", methods=["GET"])
def verify_webhook():
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")
    if mode == "subscribe" and token == VERIFY_TOKEN:
        return challenge, 200
    return "Forbidden", 403


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

        if not text:
            return jsonify({"status": "ok"}), 200

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

    except Exception as e:
        print(f"Error: {e}")

    return jsonify({"status": "ok"}), 200


@app.route("/sendpulse", methods=["POST"])
def handle_sendpulse():
    data = request.get_json()
    try:
        # SendPulse sends an array
        if isinstance(data, list):
            data = data[0]

        title = data.get("title", "")
        if title != "incoming_message":
            return jsonify({"status": "ok"}), 200

        contact = data.get("contact", {})
        contact_id = contact.get("id", "")
        phone = contact.get("phone", "") or contact.get("variables", {}).get("Phone", "")
        text = contact.get("last_message", "")

        session_key = contact_id or phone
        if not session_key or not text:
            return jsonify({"status": "ok"}), 200

        history = get_history(session_key)
        history.append({"role": "user", "content": text})

        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            system=get_system_prompt(),
            messages=history
        )

        reply = response.content[0].text
        add_message(session_key, "user", text)
        add_message(session_key, "assistant", reply)

        def reply_to_user(msg):
            if contact_id:
                send_message_by_contact(contact_id, msg)
            else:
                send_message(phone, msg)

        if "SAVE|" in reply:
            save_lines = [line for line in reply.split("\n") if line.startswith("SAVE|")]
            if save_lines:
                save_line = save_lines[0]
                from sheets import save_lead
                save_lead(save_line)
                book_calendar(session_key, save_line)
                visible_reply = reply.replace(save_line, "").strip()
                reply_to_user(visible_reply)
        else:
            reply_to_user(reply)

    except Exception as e:
        print(f"SendPulse webhook error: {e}")

    return jsonify({"status": "ok"}), 200


@app.route("/admin/clear/<phone>", methods=["GET"])
def admin_clear(phone):
    token = request.args.get("token", "")
    if token != VERIFY_TOKEN:
        return "Forbidden", 403
    clear_history(phone)
    return f"History cleared for {phone}", 200


@app.route("/admin/test-email", methods=["GET"])
def test_email():
    token = request.args.get("token", "")
    if token != VERIFY_TOKEN:
        return "Forbidden", 403
    to = request.args.get("to", "")
    if not to:
        return "Missing ?to=email", 400
    from email_sender import send_confirmation_email
    ok = send_confirmation_email(to, "בדיקה", "יום שלישי 29.04 בשעה 10:00")
    return ("Email sent OK" if ok else "Email FAILED — check logs"), 200


def book_calendar(phone, save_line):
    try:
        parts = save_line.replace("SAVE|", "").split("|")
        if len(parts) < 7:
            return
        full_name = parts[0].strip()
        availability = parts[5].strip()
        client_phone = parts[6].strip()
        client_email = parts[7].strip() if len(parts) > 7 else ""
        from cal import book_meeting, parse_availability, get_available_slots, format_slots_for_prompt
        booked = book_meeting(full_name, client_phone, availability)
        if booked:
            result = parse_availability(availability)
            if result:
                start_dt, _ = result
                day_names = ["שני", "שלישי", "רביעי", "חמישי", "שישי", "שבת", "ראשון"]
                day = day_names[start_dt.weekday()]
                time_str = start_dt.strftime("%H:%M")
                date_str = start_dt.strftime("%d.%m")
                meeting_time_str = f"יום {day} {date_str} בשעה {time_str}"
                send_message(phone, "הפגישה נקבעה! " + meeting_time_str + " - אריק יחכה לך 👍")
                if client_email and "@" in client_email:
                    from email_sender import send_confirmation_email
                    send_confirmation_email(client_email, full_name, meeting_time_str)
        else:
            # השעה תפוסה — מציעים חלופות
            slots = get_available_slots()
            if slots:
                slots_text = format_slots_for_prompt(slots[:3])
                send_message(phone, "לצערי השעה הזו כבר נתפסה 😕\nהינה אפשרויות פנויות קרובות:\n" + slots_text + "\nאיזו מתאימה לך?")
            else:
                send_message(phone, "לצערי השעה הזו כבר נתפסה 😕 אריק ייצור איתך קשר לתיאום מועד חלופי.")
    except Exception as e:
        print(f"Calendar booking error: {e}")


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

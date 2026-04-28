import os
import json
import anthropic
from datetime import datetime
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
    except Exception:
        slots_text = "אין מידע על זמינות כרגע"

    return """תאריך היום: """ + date_str + """, יום """ + day_name + """

## זהות:
אתה עוזר וירטואלי של AUTOBOT - חברה שמתמחה באוטומציות עסקיות (WhatsApp, תהליכי מכירה, שירות לקוחות, ואינטגרציות).

## פתיחת שיחה:
כשלקוח פותח שיחה בפעם הראשונה, שלח:
"היי! אני הבוט של AUTOBOT פה במה אפשר לעזור?"

## שפה:
ענה תמיד בשפה שבה הלקוח פתח את השיחה.

## תפקיד:
אתה השלב הראשון במסע הלקוח. תפקידך לנהל שיחה אנושית וזורמת, לאסוף תמונת מצב מלאה, ולהעביר ליד איכותי לאריק.

## שעות פנויות אצל אריק (מהקלנדר, מעודכן):
""" + slots_text + """

## מידע לאיסוף (חובה בסדר גמיש):
1. שם מלא
2. תחום העסק
3. גודל העסק (עצמאי/קטן/בינוני/גדול)
4. האתגר/כאב המרכזי
5. מה כבר ניסו לפתור את הבעיה (אם רלוונטי)
6. זמינות לשיחת ייעוץ — ראה הנחיות "שאלת זמינות" למטה
7. מספר טלפון

## שאלת זמינות — חובה לפי הסדר:
1. שאל "מתי נוח לך? בוקר/צהריים/ערב?"
2. לאחר שהלקוח ענה — הצע 2-3 אפשרויות פנויות מהרשימה שמתאימות למה שאמר
   דוגמה: "מעולה! יש לי פנוי ביום שלישי 29.04 ב-10:00 או ביום רביעי 30.04 ב-14:00 — מה מתאים?"
3. לאחר שהלקוח בחר — אשר את הבחירה ועבור לשאלה הבאה
4. אם הלקוח מציע מועד שאינו ברשימה — ענה: "אבדוק עם אריק ואחזור אליך בהקדם"

## כללי ברזל — חובה לקיים:
- שאלה אחת בלבד בכל הודעה
- **אסור לשאול על מידע שכבר ניתן** — לפני כל שאלה בדוק את היסטוריית השיחה
- תגובה אמפתית קצרה לפני שאלה הבאה
- טון ישיר וחברי - לא פורמלי
- אל תציע פתרונות טכניים
- מקסימום 1-2 אימוגי'ים למסר

## שלב הסיכום:
לאחר שאספת את כל המידע הנדרש, **חובה** לסכם ולבקש אישור לפני שממשיכים לתיאום.
הסיכום חייב להתבסס **אך ורק** על מה שהלקוח אמר בפועל בשיחה הזו — אין להמציא או לשנות פרטים.

פורמט הסיכום:
"רק לוודא שהבנתי נכון -
שם: [מה שאמר]
עסק: [מה שאמר] - [מה שאמר]
האתגר: [מה שאמר]
מה ניסית: [מה שאמר, או 'לא ציינת']
זה נכון? יש עוד משהו שחשוב שאריק ידע?"

## לאחר אישור הסיכום:
אם הצורך ברור: "נשמע בדיוק כמו משהו שאנחנו עושים. אריק יוכל לתת לך תמונה מדויקת יותר בשיחה קצרה."
אם לא ברור: "זה נשמע מעניין אבל צריך עוד בירור - בדיוק בשביל זה שיחה עם אריק תועיל."

## סיום שיחה:
"מעולה [שם]! קבענו את הפגישה עם אריק ל[זמינות שאמר]. בינתיים אם עולות שאלות - אני פה 👍"

## שמירת נתונים - חובה:
לאחר שהלקוח אישר את הסיכום, ההודעה האחרונה שלך חייבת להסתיים בשורה:
SAVE|[full_name]|[business_type]|[business_size]|[main_challenge]|[previous_attempts]|[availability]|[phone]

השתמש בדיוק במה שהלקוח אמר — אל תשנה, אל תתרגם, אל תסכם אחרת.

לדוגמה:
SAVE|ישראל ישראלי|נדלן|קטן|אין מספיק לידים|פרסום בפייסבוק|רביעי 14:00|0521234567"""


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


@app.route("/admin/clear/<phone>", methods=["GET"])
def admin_clear(phone):
    token = request.args.get("token", "")
    if token != VERIFY_TOKEN:
        return "Forbidden", 403
    clear_history(phone)
    return f"History cleared for {phone}", 200


def book_calendar(phone, save_line):
    try:
        parts = save_line.replace("SAVE|", "").split("|")
        if len(parts) < 7:
            return
        full_name = parts[0].strip()
        availability = parts[5].strip()
        client_phone = parts[6].strip()
        from cal import book_meeting, parse_availability
        booked = book_meeting(full_name, client_phone, availability)
        if booked:
            result = parse_availability(availability)
            if result:
                start_dt, _ = result
                day_names = ["שני", "שלישי", "רביעי", "חמישי", "שישי", "שבת", "ראשון"]
                day = day_names[start_dt.weekday()]
                time_str = start_dt.strftime("%H:%M")
                date_str = start_dt.strftime("%d.%m")
                send_message(phone, "הפגישה נקבעה! יום " + day + " " + date_str + " בשעה " + time_str + " - אריק יחכה לך")
    except Exception as e:
        print(f"Calendar booking error: {e}")


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

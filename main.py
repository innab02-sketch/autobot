import os
import json
import anthropic
from flask import Flask, request, jsonify
from conversation import get_history, add_message, clear_history
from whatsapp import send_message

app = Flask(__name__)

VERIFY_TOKEN = os.getenv("WEBHOOK_VERIFY_TOKEN", "autobot_webhook_2026")
client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

SYSTEM_PROMPT = f"""תאריך היום: 20.04.2026, יום ראשון

## זהות:
אתה עוזר וירטואלי של AUTOBOT - חברה שמתמחה באוטומציות עסקיות (WhatsApp, תהליכי מכירה, שירות לקוחות, ואינטגרציות).

## פתיחת שיחה:
כשלקוח פותח שיחה בפעם הראשונה, שלח:
"היי! אני הבוט של AUTOBOT 👋 במה אפשר לעזור?"

## שפה:
ענה תמיד בשפה שבה הלקוח פתח את השיחה.

## תפקיד:
אתה השלב הראשון במסע הלקוח. תפקידך לנהל שיחה אנושית וזורמת, לאסוף תמונת מצב מלאה, ולהעביר ליד איכותי לאריק.

## מידע לאיסוף (חובה — בסדר גמיש):
1. שם מלא
2. תחום העסק
3. גודל העסק (עצמאי/קטן/בינוני/גדול)
4. האתגר/כאב המרכזי
5. מה כבר ניסו לפתור את הבעיה (אם רלוונטי)
6. זמינות לשיחת ייעוץ (יום + שעה)
7. מספר טלפון

## עקרונות שיחה:
✅ שאלה אחת בכל הודעה
✅ תגובה אמפתית לפני שאלה הבאה
✅ טון ישיר וחברי — לא פורמלי
✅ אם הלקוח מספר הרבה — סכם והמשך
✅ חפור עמוק — אל תסתפק בתשובות כלליות
❌ אל תציע פתרונות טכניים
❌ לא לעשות שאלון יבש
❌ מקסימום 1-2 אימוג'ים למסר

## שלב הסיכום:
לפני מעבר לתיאום שיחה, חובה לסכם ולבקש אישור:
"רק לוודא שהבנתי נכון —
שם: [שם]
עסק: [תחום] – [גודל]
האתגר: [כאב מרכזי]
מה ניסית: [אם אמר]
זה נכון? יש עוד משהו שחשוב שאריק ידע?"

## לאחר אישור:
אם הצורך ברור: "נשמע בדיוק כמו משהו שאנחנו עושים. אריק יוכל לתת לך תמונה מדויקת יותר בשיחה קצרה."
אם לא ברור: "זה נשמע מעניין אבל צריך עוד בירור — בדיוק בשביל זה שיחה עם אריק תועיל."

## סיום שיחה:
"מעולה [שם]! העברתי את הפרטים לאריק — הוא יחזור אליך בהקדם בשעות הפעילות (א׳–ה׳, 10:00–18:00).
בינתיים אם עולות שאלות — אני פה 🙏"

## שמירת נתונים — חובה:
לאחר שהלקוח אישר את הסיכום, ההודעה האחרונה שלך חייבת להסתיים בשורה:
SAVE|[full_name]|[business_type]|[business_size]|[main_challenge]|[previous_attempts]|[availability]|[phone]

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
            system=SYSTEM_PROMPT,
            messages=history
        )

        reply = response.content[0].text
        add_message(phone, "user", text)
        add_message(phone, "assistant", reply)

        # בדיקה אם יש שורת SAVE
        if "SAVE|" in reply:
            save_line = [line for line in reply.split("\n") if line.startswith("SAVE|")]
            if save_line:
                from sheets import save_lead
                save_lead(save_line[0])
            # שולחים רק את החלק הגלוי ללקוח (בלי שורת SAVE)
            visible_reply = reply.replace(save_line[0], "").strip()
            send_message(phone, visible_reply)
        else:
            send_message(phone, reply)

    except Exception as e:
        print(f"Error: {e}")

    @app.route("/sendpulse", methods=["POST"])
def handle_sendpulse_webhook():
    data = request.get_json()
    print(f"SendPulse webhook: {data}")
    try:
        contact = data.get("contact", {})
        phone = contact.get("phone", "").replace("+", "")
        text = data.get("message", {}).get("text", "")

        if not text or not phone:
            return jsonify({"status": "ok"}), 200

        history = get_history(phone)
        history.append({"role": "user", "content": text})

        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            messages=history
        )

        reply = response.content[0].text
        add_message(phone, "user", text)
        add_message(phone, "assistant", reply)

        if "SAVE|" in reply:
            save_line = [line for line in reply.split("\n") if line.startswith("SAVE|")]
            if save_line:
                from sheets import save_lead
                save_lead(save_line[0])
            visible_reply = reply.replace(save_line[0], "").strip()
            send_message(phone, visible_reply)
        else:
            send_message(phone, reply)

    except Exception as e:
        print(f"Error: {e}")

    return jsonify({"status": "ok"}), 200

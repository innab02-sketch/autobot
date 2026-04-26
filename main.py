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
    return f"""תאריך היום: {date_str}, יום {day_name}

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
"מעולה [שם]! קבענו פגישה עם אריק — תקבל/י אישור עם הפרטים המדויקים.
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
            system=get_system_prompt(),
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
                try:
                    parts = save_line[0].replace("SAVE|", "").split("|")
if len(parts) >= 7:
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
                                send_message(phone, f"הפגישה נקבעה! ✅\nיום {day} {date_str} בשעה {time_str}\nאריק יחכה לך 🙌")
                except Exception as cal_err:
                    print(f"Calendar booking error: {cal_err}")
            # שולחים רק את החלק הגלוי ללקוח (בלי שורת SAVE)
            visible_reply = reply.replace(save_line[0], "").strip()
            send_message(phone, visible_reply)
        else:
            send_message(phone, reply)

    except Exception as e:
        print(f"Error: {e}")

    return jsonify({"status": "ok"}), 200


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

import os
import re
from datetime import datetime
from flask import Blueprint, request, Response
from twilio.twiml.voice_response import VoiceResponse, Gather
import anthropic
from conversation import get_history, add_message, clear_history

voice_bp = Blueprint("voice", __name__)
_ai = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

HEBREW_WEEKDAYS = ["שני", "שלישי", "רביעי", "חמישי", "שישי", "שבת", "ראשון"]
LANG = "he-IL"
# Use Twilio's Google Neural voice for Hebrew — the basic he-IL TTS produces silence.
# Google.he-IL-Wavenet-A is a female Neural voice (GA since March 2025).
VOICE = "Google.he-IL-Wavenet-A"


def _slots_text() -> str:
    try:
        from cal import get_available_slots, format_slots_for_prompt
        return format_slots_for_prompt(get_available_slots())
    except Exception:
        return "אין מידע על זמינות כרגע"


def _system_prompt(caller_phone: str) -> str:
    now = datetime.now()
    date_str = now.strftime("%d.%m.%Y")
    day_name = HEBREW_WEEKDAYS[now.weekday()]
    return f"""תאריך היום: {date_str}, יום {day_name}
טלפון המתקשר: {caller_phone}

## זהות
אתה נציג קולי של AUTOBOT — חברה שמתמחה באוטומציות עסקיות: WhatsApp, תהליכי מכירה, שירות לקוחות.
אתה מדבר בטלפון — כתוב משפטים קצרים וברורים, ללא אימוג'ים, ללא תבליטים, ללא סימנים מיוחדים.

## שפה
תמיד עברית בלבד. אל תשתמש באנגלית, אימוג'ים, כוכביות, או סימני פיסוק מיוחדים.

## תפקיד
לנהל שיחה אנושית וזורמת, לאסוף מידע על הלקוח, ולקבוע פגישת ייעוץ עם אריק.

## שעות פנויות אצל אריק (מהקלנדר):
{_slots_text()}

## מידע לאיסוף — שאלה אחת בכל פעם, בסדר גמיש
1. שם מלא
2. תחום העסק (בדיוק כפי שהלקוח מגדיר — אל תשנה)
3. גודל העסק: עצמאי / קטן / בינוני / גדול
4. האתגר המרכזי
5. מה כבר ניסו לפתור
6. זמינות: שאל "מתי נוח — בוקר, צהריים או ערב?" ואז הצע 2 אפשרויות מהרשימה למעלה בלבד
7. מייל לאישור פגישה

## כללים — חובה
- שאלה אחת בלבד בכל תגובה
- אל תשאל על מידע שכבר ניתן
- אל תציע שעה שאינה ברשימה למעלה
- אם הלקוח מציע מועד שלא ברשימה — אמור "אבדוק עם אריק ואחזור אליך"
- הטלפון כבר ידוע: {caller_phone} — אל תשאל עליו

## סיום שיחה
אחרי שהלקוח אישר את כל הפרטים:
"מצוין! קבענו פגישה עם אריק. אישור ישלח למייל שלך. תודה על הפנייה ושיהיה יום טוב!"

## שמירת נתונים — חובה לאחר אישור הלקוח
הוסף שורה בפורמט הזה בסוף התגובה האחרונה — כלום אחריה:
SAVE|[שם מלא]|[תחום עסק]|[גודל]|[אתגר]|[מה ניסו]|[זמינות שנבחרה]|{caller_phone}|[מייל]"""


def _sanitize_text(text: str) -> str:
    """Remove characters that Twilio Say verb can't handle."""
    if not text:
        return "שיהיה יום טוב"
    # Remove emoji
    text = re.sub(r'[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF\U0001F1E0-\U0001F1FF\U00002702-\U000027B0\U000024C2-\U0001F251]+', '', text)
    # Remove markdown-style formatting
    text = text.replace('*', '').replace('_', '').replace('#', '')
    # Keep only Hebrew, basic Latin, digits, and common punctuation
    text = re.sub(r'[^\u0590-\u05FF\u0020-\u007Ea-zA-Z0-9.,!?\-:;\n]', ' ', text)
    # Collapse multiple spaces
    text = re.sub(r' +', ' ', text)
    text = text.strip()
    return text if text else "שיהיה יום טוב"


def _say(twiml_node, text: str) -> None:
    """Append a <Say> with the Google Hebrew Neural voice to any TwiML node."""
    twiml_node.say(text, voice=VOICE, language=LANG)


def _gather(text: str) -> VoiceResponse:
    """Build TwiML that speaks Hebrew and waits for response."""
    text = _sanitize_text(text)
    resp = VoiceResponse()
    gather = Gather(
        input="speech",
        language=LANG,
        action="/voice/respond",
        method="POST",
        speech_timeout="auto",
    )
    # Use Google Neural voice — basic he-IL TTS produces silence on real calls.
    gather.say(text, voice=VOICE, language=LANG)
    resp.append(gather)
    # Fallback if no speech detected
    fallback = _sanitize_text("לא שמעתי. אם תרצה לחזור, התקשר שוב. שיהיה יום טוב.")
    resp.say(fallback, voice=VOICE, language=LANG)
    resp.hangup()
    return resp


@voice_bp.route("/voice/incoming", methods=["POST"])
def incoming_call():
    phone = request.form.get("From", "unknown")
    clear_history(f"voice_{phone}")
    greeting = _sanitize_text("היי, אני הנציג הוירטואלי של אוטובוט. במה אפשר לעזור?")
    return Response(
        str(_gather(greeting)),
        mimetype="text/xml",
    )


@voice_bp.route("/voice/respond", methods=["POST"])
def voice_respond():
    phone = request.form.get("From", "unknown")
    speech = request.form.get("SpeechResult", "").strip()
    session_key = f"voice_{phone}"

    if not speech:
        return Response(
            str(_gather("לא שמעתי אותך. אפשר לחזור על מה שאמרת?")),
            mimetype="text/xml",
        )

    history = get_history(session_key)
    history.append({"role": "user", "content": speech})

    try:
        ai_response = _ai.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=512,
            system=_system_prompt(phone),
            messages=history,
        )
        reply = ai_response.content[0].text
    except Exception as e:
        print(f"[voice] AI error: {e}")
        reply = "סליחה, יש תקלה טכנית. נסה להתקשר שוב בעוד כמה דקות."

    add_message(session_key, "user", speech)
    add_message(session_key, "assistant", reply)

    visible_reply = reply
    call_ended = False

    if "SAVE|" in reply:
        save_lines = [l for l in reply.split("\n") if l.startswith("SAVE|")]
        if save_lines:
            _process_save(phone, save_lines[0])
            visible_reply = reply.replace(save_lines[0], "").strip()
            call_ended = True

    resp = VoiceResponse()
    if call_ended:
        final_text = _sanitize_text(visible_reply) if visible_reply else "תודה על פנייתך. שיהיה יום טוב."
        resp.say(final_text, voice=VOICE, language=LANG)
        resp.hangup()
    else:
        resp = _gather(visible_reply)

    return Response(str(resp), mimetype="text/xml")


def _process_save(phone: str, save_line: str):
    try:
        from sheets import save_lead
        save_lead(save_line)
    except Exception as e:
        print(f"[voice] sheets error: {e}")

    try:
        parts = save_line.replace("SAVE|", "").split("|")
        if len(parts) < 8:
            return
        full_name = parts[0].strip()
        availability = parts[5].strip()
        client_email = parts[7].strip()

        from cal import parse_availability, create_event_simple
        result = parse_availability(availability)
        if result:
            start_dt, end_dt = result
            create_event_simple(full_name, phone, start_dt, end_dt, client_email)
            if client_email and "@" in client_email:
                day = HEBREW_WEEKDAYS[start_dt.weekday()]
                meeting_time_str = f"יום {day} {start_dt.strftime('%d.%m')} בשעה {start_dt.strftime('%H:%M')}"
                from email_sender import send_confirmation_email
                send_confirmation_email(client_email, full_name, meeting_time_str, start_dt, end_dt)
    except Exception as e:
        print(f"[voice] booking error: {e}")

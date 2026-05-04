import os
from datetime import datetime
from flask import Blueprint, request, Response
from twilio.twiml.voice_response import VoiceResponse, Gather
import anthropic
from conversation import get_history, add_message, clear_history

voice_bp = Blueprint("voice", __name__)
_ai = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

HEBREW_WEEKDAYS = ["שני", "שלישי", "רביעי", "חמישי", "שישי", "שבת", "ראשון"]
VOICE = "Polly.Lior-Neural"
LANG = "he-IL"


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
אתה מדבר בטלפון — כתוב משפטים קצרים וברורים, ללא אימוג'ים, ללא תבליטים.

## שפה
תמיד עברית בלבד.

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
"מצוין! קבענו פגישה עם אריק לסיום. אישור ישלח למייל שלך. תודה על הפנייה ושיהיה יום טוב!"

## שמירת נתונים — חובה לאחר אישור הלקוח
הוסף שורה בפורמט הזה בסוף התגובה האחרונה — כלום אחריה:
SAVE|[שם מלא]|[תחום עסק]|[גודל]|[אתגר]|[מה ניסו]|[זמינות שנבחרה]|{caller_phone}|[מייל]"""


def _gather(text: str) -> VoiceResponse:
    """מחזיר TwiML שמדבר ומחכה לתגובה."""
    resp = VoiceResponse()
    gather = Gather(
        input="speech",
        language=LANG,
        action="/voice/respond",
        method="POST",
        speech_timeout="auto",
        speech_model="phone_call",
    )
    gather.say(text, voice=VOICE, language=LANG)
    resp.append(gather)
    # Fallback אם לא זוהה קול
    resp.say("לא שמעתי. אם תרצה לחזור — התקשר שוב. שיהיה יום טוב!", voice=VOICE, language=LANG)
    resp.hangup()
    return resp


@voice_bp.route("/voice/incoming", methods=["POST"])
def incoming_call():
    phone = request.form.get("From", "unknown")
    clear_history(f"voice_{phone}")
    return Response(
        str(_gather("היי! אני הנציג הוירטואלי של AUTOBOT. במה אפשר לעזור?")),
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

    ai_response = _ai.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=512,
        system=_system_prompt(phone),
        messages=history,
    )
    reply = ai_response.content[0].text
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
        resp.say(visible_reply or "תודה על פנייתך. שיהיה יום טוב!", voice=VOICE, language=LANG)
        resp.hangup()
    else:
        resp = _gather(visible_reply)

    return Response(str(resp), mimetype="text/xml")


def _process_save(phone: str, save_line: str):
    try:
        from sheets import save_lead
        save_lead(save_line)
    except Exception as e:
        print(f"Voice sheets error: {e}")

    try:
        parts = save_line.replace("SAVE|", "").split("|")
        if len(parts) < 8:
            return
        full_name = parts[0].strip()
        availability = parts[5].strip()
        client_email = parts[7].strip()

        from cal import book_meeting, parse_availability
        booked = book_meeting(full_name, phone, availability)

        if booked and client_email and "@" in client_email:
            result = parse_availability(availability)
            if result:
                start_dt, _ = result
                day = HEBREW_WEEKDAYS[start_dt.weekday()]
                meeting_time_str = f"יום {day} {start_dt.strftime('%d.%m')} בשעה {start_dt.strftime('%H:%M')}"
                from email_sender import send_confirmation_email
                send_confirmation_email(client_email, full_name, meeting_time_str)
    except Exception as e:
        print(f"Voice booking error: {e}")

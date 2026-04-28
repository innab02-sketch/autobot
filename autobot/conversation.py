import json
import os

HISTORY_DIR = "conversations"
os.makedirs(HISTORY_DIR, exist_ok=True)


def _path(phone: str) -> str:
    return os.path.join(HISTORY_DIR, f"{phone}.json")


def get_history(phone: str) -> list:
    path = _path(phone)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def add_message(phone: str, role: str, content: str):
    history = get_history(phone)
    history.append({"role": role, "content": content})
    # שומרים רק 40 הודעות אחרונות
    history = history[-40:]
    with open(_path(phone), "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)


def clear_history(phone: str):
    path = _path(phone)
    if os.path.exists(path):
        os.remove(path)

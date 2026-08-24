import os
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    raise ValueError("BOT_TOKEN не задан!")

DATA_DIR = os.getenv("DATA_DIR", "/app/data")
os.makedirs(DATA_DIR, exist_ok=True)

DATABASE = os.path.join(DATA_DIR, "bot_data.db")
GROUP_ID_FILE = os.path.join(DATA_DIR, "group_id.txt")
TOPIC_ID_FILE = os.path.join(DATA_DIR, "topic_id.txt")

GROUP_CHAT_ID = os.getenv("GROUP_CHAT_ID")
if GROUP_CHAT_ID:
    GROUP_CHAT_ID = int(GROUP_CHAT_ID)

TOPIC_ID = os.getenv("TOPIC_ID")
if TOPIC_ID:
    TOPIC_ID = int(TOPIC_ID)
else:
    TOPIC_ID = None

# ПРАВИЛЬНЫЕ URL
FORUM_URLS = {
    "complaint_staff": "https://forum.vimeworld.com/forum/195-%D0%B6%D0%B0%D0%BB%D0%BE%D0%B1%D1%8B-%D0%BD%D0%B0-%D0%BF%D0%B5%D1%80%D1%81%D0%BE%D0%BD%D0%B0%D0%BB/",
    "complaint_player": "https://forum.vimeworld.com/forum/189-%D0%B6%D0%B0%D0%BB%D0%BE%D0%B1%D1%8B-%D0%BD%D0%B0-%D0%B8%D0%B3%D1%80%D0%BE%D0%BA%D0%BE%D0%B2/",
    "question_answer": "https://forum.vimeworld.com/forum/202-%D0%B2%D0%BE%D0%BF%D1%80%D0%BE%D1%81-%D0%BE%D1%82%D0%B2%D0%B5%D1%82/"
}

SECTION_NAMES = {
    "complaint_staff": "Жалобы на персонал",
    "complaint_player": "Жалобы на игроков",
    "question_answer": "Вопросы и ответы"
}

CHECK_INTERVAL = float(os.getenv("CHECK_INTERVAL", "5.0"))
REMINDER_INTERVAL = float(os.getenv("REMINDER_INTERVAL", "60.0"))

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
}

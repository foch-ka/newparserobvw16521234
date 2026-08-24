import os
from dotenv import load_dotenv

# Загружаем переменные из файла .env (если он есть)
load_dotenv()

# Токен бота — обязательный параметр
TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    raise ValueError("Переменная окружения BOT_TOKEN не задана!")

# ID группы — опционально (можно задать через переменную или через команду /setgroup)
GROUP_CHAT_ID = os.getenv("GROUP_CHAT_ID")
if GROUP_CHAT_ID:
    GROUP_CHAT_ID = int(GROUP_CHAT_ID)
else:
    GROUP_CHAT_ID = None

# Остальные настройки (URL, интервалы) можно оставить в коде,
# так как они не являются секретными и их можно публиковать.
FORUM_URLS = {
    "complaint_staff": "https://forum.vimeworld.com/forum/195-%D0%B6%D0%B0%D0%BB%D0%BE%D0%B1%D1%8B-%D0%BD%D0%B0-%D0%BF%D0%B5%D1%80%D1%81%D0%BE%D0%BD%D0%B0%D0%BB/",
    "complaint_player": "https://forum.vimeworld.com/forum/195-%D0%B6%D0%B0%D0%BB%D0%BE%D0%B1%D1%8B-%D0%BD%D0%B0-%D0%BF%D0%B5%D1%80%D1%81%D0%BE%D0%BD%D0%B0%D0%BB/",  # замените на реальный URL
    "question_answer": "https://forum.vimeworld.com/forum/202-%D0%B2%D0%BE%D0%BF%D1%80%D0%BE%D1%81-%D0%BE%D1%82%D0%B2%D0%B5%D1%82/"
}

SECTION_NAMES = {
    "complaint_staff": "Жалобы на персонал",
    "complaint_player": "Жалобы на игроков",
    "question_answer": "Вопросы и ответы"
}

CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", "5"))      # минуты
REMINDER_INTERVAL = int(os.getenv("REMINDER_INTERVAL", "60")) # минуты
DATABASE = os.getenv("DATABASE", "bot_data.db")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
}

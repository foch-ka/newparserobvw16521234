import requests
import asyncio
from telegram import Bot
from bs4 import BeautifulSoup
from config import TOKEN, HEADERS, GROUP_CHAT_ID

bot = Bot(token=TOKEN)

def send_notification(text):
    """Отправляет сообщение только в группу (если GROUP_CHAT_ID задан)."""
    if GROUP_CHAT_ID is None:
        print("GROUP_CHAT_ID не задан, сообщение не отправлено.")
        return
    try:
        asyncio.run(bot.send_message(chat_id=GROUP_CHAT_ID, text=text, parse_mode="Markdown"))
    except Exception as e:
        print(f"Ошибка отправки в группу {GROUP_CHAT_ID}: {e}")

def is_topic_closed_on_page(topic_url):
    try:
        resp = requests.get(topic_url, headers=HEADERS, timeout=10)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        if soup.find(string=lambda t: t and "закрыта" in t and "сообщений" in t):
            return True
        if soup.select_one("i.fa-lock"):
            return True
        return False
    except Exception as e:
        print(f"Ошибка при проверке закрытости темы {topic_url}: {e}")
        return False

def extract_topic_id_from_url(url):
    parts = url.split("/")
    for part in parts:
        if part.startswith("topic-"):
            return part.split("-")[1]
        elif part.isdigit() and len(part) > 4:
            return part
    return None

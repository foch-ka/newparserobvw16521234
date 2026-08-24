import logging
import aiohttp
from bs4 import BeautifulSoup
from telegram import Bot
from config import TOKEN, HEADERS, GROUP_CHAT_ID, TOPIC_ID
from database import get_ping_users

logger = logging.getLogger(__name__)
bot = Bot(token=TOKEN)

async def send_notification(text):
    logger.info(f"send_notification: GROUP_CHAT_ID={GROUP_CHAT_ID}, TOPIC_ID={TOPIC_ID}")
    if GROUP_CHAT_ID is None:
        logger.warning("GROUP_CHAT_ID не задан")
        return

    ping_users = get_ping_users(GROUP_CHAT_ID)
    mentions = []
    for user in ping_users:
        user_id = user['user_id']
        username = user.get('username', str(user_id))
        mentions.append(f'<a href="tg://user?id={user_id}">@{username}</a>')

    if mentions:
        text += "\n\n🔔 Упоминания: " + " ".join(mentions)

    try:
        result = await bot.send_message(
            chat_id=GROUP_CHAT_ID,
            text=text,
            parse_mode="HTML",
            message_thread_id=TOPIC_ID,
            disable_web_page_preview=True
        )
        logger.info(f"✅ Сообщение отправлено, ID: {result.message_id}")
    except Exception as e:
        logger.error(f"❌ Ошибка отправки: {e}", exc_info=True)

async def is_topic_closed_on_page(topic_url):
    logger.debug(f"Проверка закрытости: {topic_url}")
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(topic_url, headers=HEADERS, timeout=10) as resp:
                html = await resp.text()
                soup = BeautifulSoup(html, "html.parser")
                if soup.find(string=lambda t: t and ("закрыта" in t or "closed" in t.lower()) and "сообщений" in t):
                    return True
                if soup.select_one("i.fa-lock"):
                    return True
                if soup.select_one("[class*='closed']"):
                    return True
                return False
    except Exception as e:
        logger.error(f"Ошибка при проверке закрытости: {e}")
        return False

def extract_topic_id_from_url(url):
    import re
    match = re.search(r'/topic/(\d+)-', url)
    if match:
        return match.group(1)
    return None

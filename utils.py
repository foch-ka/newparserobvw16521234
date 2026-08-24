import logging
import aiohttp
from bs4 import BeautifulSoup
from telegram import Bot
from config import TOKEN, HEADERS, GROUP_CHAT_ID, TOPIC_ID
from database import get_ping_users

logger = logging.getLogger(__name__)
bot = Bot(token=TOKEN)

async def send_notification(text):
    logger.info(f"send_notification вызвана, GROUP_CHAT_ID={GROUP_CHAT_ID}, TOPIC_ID={TOPIC_ID}")
    if GROUP_CHAT_ID is None:
        logger.warning("GROUP_CHAT_ID не задан, сообщение не отправлено.")
        return

    ping_users = get_ping_users(GROUP_CHAT_ID)
    logger.info(f"Найдено {len(ping_users)} пользователей для пинга")
    mentions = []
    for user in ping_users:
        user_id = user['user_id']
        username = user.get('username', str(user_id))
        mentions.append(f"[@{username}](tg://user?id={user_id})")

    if mentions:
        text += "\n\n🔔 Упоминания: " + " ".join(mentions)

    try:
        # Отправка с указанием темы, если TOPIC_ID задан
        await bot.send_message(
            chat_id=GROUP_CHAT_ID,
            text=text,
            parse_mode="Markdown",
            message_thread_id=TOPIC_ID  # если None – игнорируется
        )
        logger.info(f"Уведомление отправлено в группу {GROUP_CHAT_ID}, тема {TOPIC_ID}")
    except Exception as e:
        logger.error(f"Ошибка отправки в группу {GROUP_CHAT_ID}: {e}", exc_info=True)

async def is_topic_closed_on_page(topic_url):
    logger.debug(f"Проверка закрытости темы: {topic_url}")
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(topic_url, headers=HEADERS, timeout=10) as resp:
                html = await resp.text()
                soup = BeautifulSoup(html, "html.parser")
                if soup.find(string=lambda t: t and "закрыта" in t and "сообщений" in t):
                    return True
                if soup.select_one("i.fa-lock"):
                    return True
                return False
    except Exception as e:
        logger.error(f"Ошибка при проверке закрытости темы {topic_url}: {e}", exc_info=True)
        return False

def extract_topic_id_from_url(url):
    parts = url.split("/")
    for part in parts:
        if part.startswith("topic-"):
            return part.split("-")[1]
        elif part.isdigit() and len(part) > 4:
            return part
    return None

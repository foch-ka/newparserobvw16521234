import logging
import aiohttp
from bs4 import BeautifulSoup
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from config import TOKEN, HEADERS, GROUP_CHAT_ID, TOPIC_ID
from database import get_ping_users
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)
bot = Bot(token=TOKEN)

MENTIONS_PER_MESSAGE = 5

MOSCOW_TZ = timezone(timedelta(hours=3))

def get_moscow_time(dt=None):
    if dt is None:
        dt = datetime.utcnow()
    if isinstance(dt, str):
        try:
            dt = datetime.fromisoformat(dt)
        except ValueError:
            dt = datetime.utcnow()
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(MOSCOW_TZ)

def format_moscow_time(dt=None):
    msk_time = get_moscow_time(dt)
    return msk_time.strftime("%d.%m.%Y %H:%M")

async def send_notification(text, topic_id=None):
    logger.info(f"send_notification: GROUP_CHAT_ID={GROUP_CHAT_ID}, TOPIC_ID={TOPIC_ID}, topic_id={topic_id}")
    if GROUP_CHAT_ID is None:
        logger.warning("GROUP_CHAT_ID не задан")
        return

    reply_markup = None
    if topic_id:
        keyboard = [[InlineKeyboardButton("🔒 Закрою", callback_data=f"close_topic_{topic_id}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

    ping_users = get_ping_users(GROUP_CHAT_ID)
    if not ping_users:
        try:
            result = await bot.send_message(
                chat_id=GROUP_CHAT_ID,
                text=text,
                parse_mode="HTML",
                message_thread_id=TOPIC_ID,
                disable_web_page_preview=True,
                reply_markup=reply_markup
            )
            logger.info(f"✅ Сообщение отправлено (без пингов), ID: {result.message_id}")
        except Exception as e:
            logger.error(f"❌ Ошибка отправки: {e}", exc_info=True)
        return

    all_mentions = []
    for user in ping_users:
        user_id = user['user_id']
        username = user['username']
        if user_id and user_id > 0:
            if username:
                all_mentions.append(f'<a href="tg://user?id={user_id}">@{username}</a>')
            else:
                all_mentions.append(f'<a href="tg://user?id={user_id}">пользователь</a>')
        elif username:
            all_mentions.append(f'@{username}')
        else:
            continue

    if not all_mentions:
        try:
            result = await bot.send_message(
                chat_id=GROUP_CHAT_ID,
                text=text,
                parse_mode="HTML",
                message_thread_id=TOPIC_ID,
                disable_web_page_preview=True,
                reply_markup=reply_markup
            )
            logger.info(f"✅ Сообщение отправлено (без пингов), ID: {result.message_id}")
        except Exception as e:
            logger.error(f"❌ Ошибка отправки: {e}", exc_info=True)
        return

    chunks = [all_mentions[i:i + MENTIONS_PER_MESSAGE] for i in range(0, len(all_mentions), MENTIONS_PER_MESSAGE)]

    for idx, chunk in enumerate(chunks):
        mentions_text = " ".join(chunk)
        if idx == 0:
            if len(chunks) > 1:
                full_text = f"{text}\n\n🔔 Упоминания (часть 1/{len(chunks)}): {mentions_text}"
            else:
                full_text = f"{text}\n\n🔔 Упоминания: {mentions_text}"
            markup = reply_markup
        else:
            full_text = f"🔔 Упоминания (часть {idx+1}/{len(chunks)}): {mentions_text}"
            markup = None

        try:
            result = await bot.send_message(
                chat_id=GROUP_CHAT_ID,
                text=full_text,
                parse_mode="HTML",
                message_thread_id=TOPIC_ID,
                disable_web_page_preview=True,
                reply_markup=markup
            )
            logger.info(f"✅ Сообщение отправлено (часть {idx+1}), ID: {result.message_id}")
        except Exception as e:
            logger.error(f"❌ Ошибка отправки (часть {idx+1}): {e}", exc_info=True)

async def send_personal_reminder(text, user_id, username=None):
    logger.info(f"send_personal_reminder: GROUP_CHAT_ID={GROUP_CHAT_ID}, user_id={user_id}")
    if GROUP_CHAT_ID is None:
        logger.warning("GROUP_CHAT_ID не задан")
        return

    if username:
        mention = f'<a href="tg://user?id={user_id}">@{username}</a>'
    else:
        mention = f'<a href="tg://user?id={user_id}">пользователь</a>'

    full_text = f"{text}\n\n🔔 Напоминание для {mention}"

    try:
        result = await bot.send_message(
            chat_id=GROUP_CHAT_ID,
            text=full_text,
            parse_mode="HTML",
            message_thread_id=TOPIC_ID,
            disable_web_page_preview=True
        )
        logger.info(f"✅ Персональное напоминание отправлено, ID: {result.message_id}")
    except Exception as e:
        logger.error(f"❌ Ошибка отправки персонального напоминания: {e}", exc_info=True)

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
        logger.error(f"Ошибка при проверке закрытости {topic_url}: {e}")
        return False

def extract_topic_id_from_url(url):
    import re
    match = re.search(r'/topic/(\d+)-', url)
    if match:
        return match.group(1)
    return None

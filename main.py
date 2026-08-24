import asyncio
import os
import logging
from datetime import datetime, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from telegram.ext import Application

from config import TOKEN, CHECK_INTERVAL, REMINDER_INTERVAL, GROUP_CHAT_ID, TOPIC_ID, GROUP_ID_FILE, TOPIC_ID_FILE, DATA_DIR, FORUM_URLS
from database import init_db, get_topics_for_reminder, mark_reminder_sent, update_topic_closed_status, get_db_connection
from parser import parse_section
from utils import send_notification, is_topic_closed_on_page
from bot_handlers import register_handlers
from logger import setup_logger

# Настройка логирования
logger = setup_logger()
logger.info(f"Папка данных: {DATA_DIR}")

# Инициализация БД
init_db()
logger.info("База данных инициализирована")

# Загрузка ID группы и темы из файлов
if os.path.exists(GROUP_ID_FILE):
    with open(GROUP_ID_FILE, "r") as f:
        saved_group = f.read().strip()
        if saved_group:
            import config
            config.GROUP_CHAT_ID = int(saved_group)
            logger.info(f"Загружен ID группы: {config.GROUP_CHAT_ID}")

if os.path.exists(TOPIC_ID_FILE):
    with open(TOPIC_ID_FILE, "r") as f:
        saved_topic = f.read().strip()
        if saved_topic and saved_topic != "0":
            import config
            config.TOPIC_ID = int(saved_topic)
            logger.info(f"Загружен ID темы: {config.TOPIC_ID}")
        elif saved_topic == "0":
            config.TOPIC_ID = None

logger.info(f"CHECK_INTERVAL={CHECK_INTERVAL} мин, REMINDER_INTERVAL={REMINDER_INTERVAL} мин")
logger.info(f"GROUP_CHAT_ID={GROUP_CHAT_ID}, TOPIC_ID={TOPIC_ID}")

async def run_parsers():
    """Запускает парсинг всех разделов."""
    logger.info("Запуск парсеров...")
    for key in FORUM_URLS:
        logger.info(f"Парсинг: {key} -> {FORUM_URLS[key]}")
        await parse_section(key)

async def check_reminders():
    """Проверяет темы, которым уже >24 часов, и отправляет повторные уведомления."""
    logger.info("=== Проверка напоминаний ===")
    try:
        # Логируем все темы из БД для отладки
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("SELECT topic_id, title, first_notified, reminder_sent, is_closed FROM pending_reminders")
        all_rows = c.fetchall()
        conn.close()
        logger.info(f"Всего тем в БД: {len(all_rows)}")
        for row in all_rows:
            logger.info(f"Тема: {row['title']}, first_notified: {row['first_notified']}, "
                        f"reminder_sent: {row['reminder_sent']}, is_closed: {row['is_closed']}")

        # Получаем темы, которые уже готовы к повторному уведомлению
        topics = get_topics_for_reminder()
        logger.info(f"Тем для напоминания (по условиям): {len(topics)}")
        for topic in topics:
            topic_id, section_key, title, author, url = topic
            logger.info(f"Проверка: {title} (ID: {topic_id})")
            is_closed = await is_topic_closed_on_page(url)
            if is_closed:
                update_topic_closed_status(topic_id, is_closed=True)
                logger.info(f"Тема '{title}' закрыта, обновлено is_closed=1")
            else:
                msg = f"⏰ <b>Есть не закрытая тема!</b>\n\n" \
                      f"<b>Название:</b> {title}\n" \
                      f"<b>Автор:</b> {author}\n" \
                      f"<a href='{url}'>Ссылка</a>"
                await send_notification(msg)
                mark_reminder_sent(topic_id)
                logger.info(f"Повторное уведомление для '{title}' отправлено")
    except Exception as e:
        logger.error(f"Ошибка в check_reminders: {e}", exc_info=True)

async def scheduled_jobs():
    """Планировщик задач."""
    scheduler = AsyncIOScheduler()
    scheduler.add_job(run_parsers, 'interval', minutes=CHECK_INTERVAL)
    scheduler.add_job(check_reminders, 'interval', minutes=REMINDER_INTERVAL)
    scheduler.start()
    logger.info(f"Планировщик запущен.")
    # Первый запуск сразу
    await run_parsers()
    while True:
        await asyncio.sleep(60)

async def run_bot():
    """Запуск Telegram-бота."""
    logger.info("Запуск Telegram-бота...")
    try:
        app = Application.builder().token(TOKEN).build()
        register_handlers(app)
        await app.initialize()
        await app.start()
        await app.updater.start_polling()
        logger.info("Бот запущен и слушает сообщения.")
        while True:
            await asyncio.sleep(1)
    except Exception as e:
        logger.error(f"Ошибка в run_bot: {e}", exc_info=True)

async def main():
    logger.info("=== Бот запущен ===")
    await asyncio.gather(run_bot(), scheduled_jobs())

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Остановлен.")
    except Exception as e:
        logger.error(f"Ошибка запуска: {e}", exc_info=True)

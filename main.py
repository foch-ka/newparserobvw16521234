import asyncio
import os
import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from telegram.ext import Application

from config import TOKEN, CHECK_INTERVAL, REMINDER_INTERVAL, GROUP_CHAT_ID, TOPIC_ID, GROUP_ID_FILE, TOPIC_ID_FILE, DATA_DIR
from database import init_db, get_topics_for_reminder, mark_reminder_sent, update_topic_closed_status
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

# Загрузка ID группы и темы из файлов (если они есть)
if os.path.exists(GROUP_ID_FILE):
    with open(GROUP_ID_FILE, "r") as f:
        saved_group = f.read().strip()
        if saved_group:
            import config
            config.GROUP_CHAT_ID = int(saved_group)
            logger.info(f"Загружен ID группы из файла: {config.GROUP_CHAT_ID}")

if os.path.exists(TOPIC_ID_FILE):
    with open(TOPIC_ID_FILE, "r") as f:
        saved_topic = f.read().strip()
        if saved_topic and saved_topic != "0":
            import config
            config.TOPIC_ID = int(saved_topic)
            logger.info(f"Загружен ID темы из файла: {config.TOPIC_ID}")
        elif saved_topic == "0":
            config.TOPIC_ID = None
            logger.info("Установлен общий чат (без темы)")

# Логируем текущие настройки
logger.info(f"Загружены интервалы: CHECK_INTERVAL={CHECK_INTERVAL} мин, REMINDER_INTERVAL={REMINDER_INTERVAL} мин")
logger.info(f"Текущий GROUP_CHAT_ID={GROUP_CHAT_ID}, TOPIC_ID={TOPIC_ID}")

async def run_parsers():
    logger.info("Запуск парсеров...")
    try:
        await parse_section("complaint_staff")
        await parse_section("complaint_player")
        await parse_section("question_answer")
    except Exception as e:
        logger.error(f"Ошибка при парсинге: {e}", exc_info=True)

async def check_reminders():
    logger.info("Проверка напоминаний...")
    try:
        topics = get_topics_for_reminder()
        logger.info(f"Найдено тем для напоминания: {len(topics)}")
        for topic in topics:
            topic_id, section_key, title, author, url = topic
            logger.info(f"Проверка темы '{title}' (ID {topic_id})")
            if await is_topic_closed_on_page(url):
                update_topic_closed_status(topic_id, is_closed=True)
                logger.info(f"Тема '{title}' закрыта, повторное уведомление не отправляем.")
            else:
                message = f"⏰ **Напоминание!**\n\nТема **'{title}'** от **{author}** всё ещё открыта.\nСсылка: {url}"
                await send_notification(message)
                mark_reminder_sent(topic_id)
                logger.info(f"Отправлено повторное уведомление для темы '{title}'.")
    except Exception as e:
        logger.error(f"Ошибка при проверке напоминаний: {e}", exc_info=True)

async def scheduled_jobs():
    scheduler = AsyncIOScheduler()
    scheduler.add_job(run_parsers, 'interval', minutes=CHECK_INTERVAL)
    scheduler.add_job(check_reminders, 'interval', minutes=REMINDER_INTERVAL)
    scheduler.start()
    logger.info(f"Планировщик запущен: парсинг каждые {CHECK_INTERVAL} мин, напоминания каждые {REMINDER_INTERVAL} мин.")
    await run_parsers()  # первый запуск сразу
    while True:
        await asyncio.sleep(60)

async def run_bot():
    logger.info("Запуск Telegram-бота...")
    app = Application.builder().token(TOKEN).build()
    register_handlers(app)
    await app.initialize()
    await app.start()
    await app.updater.start_polling()
    logger.info("Бот успешно запущен и слушает сообщения.")
    try:
        while True:
            await asyncio.sleep(1)
    except Exception as e:
        logger.error(f"Ошибка в работе бота: {e}", exc_info=True)
    finally:
        await app.stop()

async def main():
    logger.info("=== Бот запущен ===")
    await asyncio.gather(run_bot(), scheduled_jobs())

if __name__ == "__main__":
    asyncio.run(main())

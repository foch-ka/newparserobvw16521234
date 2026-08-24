import asyncio
import threading
import os
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from telegram.ext import Application

from config import TOKEN, CHECK_INTERVAL, REMINDER_INTERVAL, GROUP_CHAT_ID
from database import init_db, get_topics_for_reminder, mark_reminder_sent, update_topic_closed_status
from parser import parse_section
from utils import send_notification, is_topic_closed_on_page
from bot_handlers import register_handlers

init_db()

if os.path.exists("group_id.txt"):
    with open("group_id.txt", "r") as f:
        saved_id = f.read().strip()
        if saved_id:
            import config
            config.GROUP_CHAT_ID = int(saved_id)
            print(f"Загружен ID группы: {config.GROUP_CHAT_ID}")

async def run_parsers():
    print("Запуск парсеров...")
    parse_section("complaint_staff")
    parse_section("complaint_player")
    parse_section("question_answer")

async def check_reminders():
    print("Проверка напоминаний...")
    topics = get_topics_for_reminder()
    for topic in topics:
        topic_id, section_key, title, author, url = topic
        if is_topic_closed_on_page(url):
            update_topic_closed_status(topic_id, is_closed=True)
            print(f"Тема '{title}' закрыта, повторное уведомление не отправляем.")
        else:
            message = f"⏰ **Напоминание!**\n\nТема **'{title}'** от **{author}** всё ещё открыта.\nСсылка: {url}"
            send_notification(message)
            mark_reminder_sent(topic_id)
            print(f"Отправлено повторное уведомление для темы '{title}'.")

async def scheduled_jobs():
    scheduler = AsyncIOScheduler()
    scheduler.add_job(run_parsers, 'interval', minutes=CHECK_INTERVAL)
    scheduler.add_job(check_reminders, 'interval', minutes=REMINDER_INTERVAL)
    scheduler.start()
    await run_parsers()
    while True:
        await asyncio.sleep(60)

def run_bot():
    app = Application.builder().token(TOKEN).build()
    register_handlers(app)
    print("Бот запущен...")
    app.run_polling()

if __name__ == "__main__":
    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()
    asyncio.run(scheduled_jobs())

import logging
import os
from telegram import Update, ChatMember
from telegram.ext import Application, CommandHandler, ContextTypes
from config import GROUP_CHAT_ID, GROUP_ID_FILE, TOPIC_ID_FILE
from database import (
    add_ping_user, remove_ping_user, get_ping_users,
    get_all_topics, get_all_pending_topics, mark_reminder_sent
)
from utils import send_notification

logger = logging.getLogger(__name__)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"/start от {update.effective_user.id}")
    await update.message.reply_html(
        "👋 Я бот для отслеживания новых тем на форуме VimeWorld.\n\n"
        "<b>Команды для администраторов:</b>\n"
        "/setgroup – установить текущую группу и тему\n"
        "/addping – добавить пользователя (реплай, ID или @username)\n"
        "/removeping – удалить пользователя\n"
        "/listpings – список пользователей для упоминаний\n"
        "/test – отправить тестовое сообщение\n"
        "/forceremind – принудительно отправить напоминания (для всех открытых тем)\n"
        "/showdb – показать все темы из БД"
    )

async def setgroup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    topic_id = update.effective_message.message_thread_id
    logger.info(f"/setgroup от {user.id} в {chat.id}, тема {topic_id}")

    if chat.type not in ["group", "supergroup"]:
        await update.message.reply_html("⚠️ Только в группах.")
        return

    try:
        member = await chat.get_member(user.id)
        if member.status not in [ChatMember.ADMINISTRATOR, ChatMember.OWNER]:
            await update.message.reply_html("⛔ Только администраторы.")
            return
    except Exception as e:
        logger.error(f"Ошибка прав: {e}")
        await update.message.reply_html("❌ Не удалось проверить права.")
        return

    with open(GROUP_ID_FILE, "w") as f:
        f.write(str(chat.id))
    with open(TOPIC_ID_FILE, "w") as f:
        f.write(str(topic_id) if topic_id is not None else "0")

    global GROUP_CHAT_ID, TOPIC_ID
    GROUP_CHAT_ID = chat.id
    TOPIC_ID = topic_id
    import config
    config.GROUP_CHAT_ID = chat.id
    config.TOPIC_ID = topic_id

    await update.message.reply_html(
        f"✅ Группа и тема установлены.\n"
        f"ID группы: <code>{chat.id}</code>\n"
        f"ID темы: <code>{topic_id if topic_id is not None else '0 (общий чат)'}</code>"
    )

async def addping(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    logger.info(f"/addping от {user.id}")

    if chat.type not in ["group", "supergroup"]:
        await update.message.reply_html("⚠️ Только в группах.")
        return

    try:
        member = await chat.get_member(user.id)
        if member.status not in [ChatMember.ADMINISTRATOR, ChatMember.OWNER]:
            await update.message.reply_html("⛔ Только администраторы.")
            return
    except Exception:
        await update.message.reply_html("❌ Ошибка прав.")
        return

    target_user_id = None
    target_username = None

    if update.message.reply_to_message:
        target_user_id = update.message.reply_to_message.from_user.id
        target_username = update.message.reply_to_message.from_user.username
    elif context.args:
        arg = context.args[0]
        if arg.startswith('@'):
            try:
                chat_member = await chat.get_member(arg)
                target_user_id = chat_member.user.id
                target_username = arg[1:]
            except Exception:
                await update.message.reply_html("Не найден пользователь.")
                return
        else:
            try:
                target_user_id = int(arg)
                try:
                    chat_member = await chat.get_member(target_user_id)
                    target_username = chat_member.user.username
                except:
                    target_username = None
            except ValueError:
                await update.message.reply_html("Некорректный ID.")
                return
    else:
        await update.message.reply_html("Укажите пользователя (ID или @username) или ответьте на его сообщение.")
        return

    if target_user_id is None:
        await update.message.reply_html("Не удалось определить пользователя.")
        return

    add_ping_user(chat.id, target_user_id, target_username, added_by=user.id)
    await update.message.reply_html(f"✅ Пользователь {target_username or target_user_id} добавлен.")

async def removeping(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    logger.info(f"/removeping от {user.id}")

    if chat.type not in ["group", "supergroup"]:
        await update.message.reply_html("⚠️ Только в группах.")
        return

    try:
        member = await chat.get_member(user.id)
        if member.status not in [ChatMember.ADMINISTRATOR, ChatMember.OWNER]:
            await update.message.reply_html("⛔ Только администраторы.")
            return
    except Exception:
        await update.message.reply_html("❌ Ошибка прав.")
        return

    target_user_id = None
    if update.message.reply_to_message:
        target_user_id = update.message.reply_to_message.from_user.id
    elif context.args:
        arg = context.args[0]
        if arg.startswith('@'):
            try:
                chat_member = await chat.get_member(arg)
                target_user_id = chat_member.user.id
            except Exception:
                await update.message.reply_html("Не найден пользователь.")
                return
        else:
            try:
                target_user_id = int(arg)
            except ValueError:
                await update.message.reply_html("Некорректный ID.")
                return
    else:
        await update.message.reply_html("Укажите пользователя (ID или @username) или ответьте на его сообщение.")
        return

    if target_user_id is None:
        await update.message.reply_html("Не удалось определить пользователя.")
        return

    remove_ping_user(chat.id, target_user_id)
    await update.message.reply_html("✅ Пользователь удалён.")

async def listpings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    logger.info(f"/listpings от {update.effective_user.id}")

    if chat.type not in ["group", "supergroup"]:
        await update.message.reply_html("⚠️ Только в группах.")
        return

    pings = get_ping_users(chat.id)
    if not pings:
        await update.message.reply_html("📭 Список пуст.")
        return

    text = "📋 Список пользователей для упоминаний:\n"
    for ping in pings:
        username = ping['username'] or str(ping['user_id'])
        text += f"- @{username} (ID: {ping['user_id']})\n"
    await update.message.reply_html(text)

async def test(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"/test от {update.effective_user.id}")
    await update.message.reply_html("🔄 Отправляю тестовое сообщение...")
    await send_notification("🧪 <b>Тестовое сообщение</b> от бота. Если вы его видите – всё работает!")
    await update.message.reply_html("✅ Тестовое сообщение отправлено.")

async def forceremind(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"/forceremind от {update.effective_user.id}")
    try:
        # БЕРЁМ ВСЕ ТЕМЫ, НЕЗАВИСИМО ОТ ВРЕМЕНИ
        topics = get_all_pending_topics()
        if not topics:
            await update.message.reply_html("📭 Нет открытых тем для напоминания.")
            return
        count = 0
        for topic in topics:
            topic_id, section_key, title, author, url = topic
            msg = f"⏰ <b>Есть не закрытая тема!</b>\n\n" \
                  f"<b>Название:</b> {title}\n" \
                  f"<b>Автор:</b> {author}\n" \
                  f"<a href='{url}'>Ссылка</a>"
            await send_notification(msg)
            mark_reminder_sent(topic_id)
            count += 1
        await update.message.reply_html(f"✅ Отправлено напоминаний: {count}")
    except Exception as e:
        logger.error(f"Ошибка в /forceremind: {e}", exc_info=True)
        await update.message.reply_html(f"❌ Ошибка: {e}")

async def showdb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"/showdb от {update.effective_user.id}")
    try:
        rows = get_all_topics()
        if not rows:
            await update.message.reply_html("📭 База данных пуста.")
            return
        text = "📋 <b>Темы в БД:</b>\n\n"
        for row in rows:
            text += f"ID: <code>{row['topic_id']}</code>\n"
            text += f"Название: {row['title']}\n"
            text += f"Первое уведомление: {row['first_notified']}\n"
            text += f"Напомнено: {row['reminder_sent']}, Закрыта: {row['is_closed']}\n"
            text += "---\n"
            if len(text) > 3500:
                text += "... (слишком много тем, обрезано)"
                break
        await update.message.reply_html(text)
    except Exception as e:
        logger.error(f"Ошибка в /showdb: {e}", exc_info=True)
        await update.message.reply_html(f"❌ Ошибка: {e}")

def register_handlers(app: Application):
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("setgroup", setgroup))
    app.add_handler(CommandHandler("addping", addping))
    app.add_handler(CommandHandler("removeping", removeping))
    app.add_handler(CommandHandler("listpings", listpings))
    app.add_handler(CommandHandler("test", test))
    app.add_handler(CommandHandler("forceremind", forceremind))
    app.add_handler(CommandHandler("showdb", showdb))

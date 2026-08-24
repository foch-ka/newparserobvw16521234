import logging
import os
from telegram import Update, ChatMember
from telegram.ext import Application, CommandHandler, ContextTypes
from config import GROUP_CHAT_ID, TOPIC_ID, GROUP_ID_FILE, TOPIC_ID_FILE
from database import add_ping_user, remove_ping_user, get_ping_users
from utils import send_notification

logger = logging.getLogger(__name__)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"Команда /start от {update.effective_user.id} в чате {update.effective_chat.id}")
    await update.message.reply_text(
        "👋 Я бот для отслеживания новых тем на форуме VimeWorld.\n\n"
        "Команды для администраторов:\n"
        "/setgroup – установить текущую группу и тему для уведомлений\n"
        "/addping – добавить пользователя для упоминания (через реплай, ID или @username)\n"
        "/removeping – удалить пользователя\n"
        "/listpings – показать список пользователей для упоминаний\n"
        "/test – отправить тестовое сообщение в группу (для проверки)"
    )

async def setgroup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    # Получаем ID темы, из которой вызвана команда (если есть)
    topic_id = update.effective_message.message_thread_id
    logger.info(f"Команда /setgroup от {user.id} в чате {chat.id}, тема {topic_id} (тип чата: {chat.type})")

    if chat.type not in ["group", "supergroup"]:
        await update.message.reply_text("⚠️ Эта команда работает только в группах.")
        return

    try:
        member = await chat.get_member(user.id)
        if member.status not in [ChatMember.ADMINISTRATOR, ChatMember.OWNER]:
            await update.message.reply_text("⛔ Только администраторы группы могут использовать эту команду.")
            return
    except Exception as e:
        logger.error(f"Ошибка проверки прав: {e}")
        await update.message.reply_text("❌ Не удалось проверить ваши права.")
        return

    # Сохраняем ID группы
    with open(GROUP_ID_FILE, "w") as f:
        f.write(str(chat.id))
    # Сохраняем ID темы (если есть) – если None, пишем 0 (означает общий чат)
    with open(TOPIC_ID_FILE, "w") as f:
        f.write(str(topic_id) if topic_id is not None else "0")

    # Обновляем глобальные переменные
    global GROUP_CHAT_ID, TOPIC_ID
    GROUP_CHAT_ID = chat.id
    TOPIC_ID = topic_id
    import config
    config.GROUP_CHAT_ID = chat.id
    config.TOPIC_ID = topic_id

    await update.message.reply_text(
        f"✅ Группа и тема установлены.\n"
        f"ID группы: {chat.id}\n"
        f"ID темы: {topic_id if topic_id is not None else '0 (общий чат)'}"
    )
    logger.info(f"Установлены: группа {chat.id}, тема {topic_id}")

async def addping(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    logger.info(f"Команда /addping от {user.id} в чате {chat.id}")

    if chat.type not in ["group", "supergroup"]:
        await update.message.reply_text("⚠️ Эта команда работает только в группах.")
        return

    try:
        member = await chat.get_member(user.id)
        if member.status not in [ChatMember.ADMINISTRATOR, ChatMember.OWNER]:
            await update.message.reply_text("⛔ Только администраторы могут использовать эту команду.")
            return
    except Exception as e:
        logger.error(f"Ошибка проверки прав: {e}")
        await update.message.reply_text("❌ Не удалось проверить ваши права.")
        return

    target_user_id = None
    target_username = None

    if update.message.reply_to_message:
        target_user_id = update.message.reply_to_message.from_user.id
        target_username = update.message.reply_to_message.from_user.username
        logger.info(f"Целевой пользователь определён из реплая: {target_user_id} ({target_username})")
    else:
        args = context.args
        if not args:
            await update.message.reply_text("Укажите пользователя (ID или @username) или ответьте на его сообщение.")
            return
        arg = args[0]
        if arg.startswith('@'):
            try:
                chat_member = await chat.get_member(arg)
                target_user_id = chat_member.user.id
                target_username = arg[1:]
                logger.info(f"Целевой пользователь найден по username: {target_user_id}")
            except Exception as e:
                logger.error(f"Не найден пользователь {arg}: {e}")
                await update.message.reply_text("Не удалось найти пользователя с таким username в этой группе.")
                return
        else:
            try:
                target_user_id = int(arg)
                try:
                    chat_member = await chat.get_member(target_user_id)
                    target_username = chat_member.user.username
                except:
                    target_username = None
                logger.info(f"Целевой пользователь найден по ID: {target_user_id}")
            except ValueError:
                await update.message.reply_text("Некорректный ID. Введите число или @username.")
                return

    if target_user_id is None:
        await update.message.reply_text("Не удалось определить пользователя.")
        return

    add_ping_user(chat.id, target_user_id, target_username, added_by=user.id)
    logger.info(f"Пользователь {target_user_id} ({target_username}) добавлен в пинги администратором {user.id} в группе {chat.id}")
    await update.message.reply_text(f"✅ Пользователь {target_username or target_user_id} добавлен в список упоминаний.")

async def removeping(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    logger.info(f"Команда /removeping от {user.id} в чате {chat.id}")

    if chat.type not in ["group", "supergroup"]:
        await update.message.reply_text("⚠️ Эта команда работает только в группах.")
        return

    try:
        member = await chat.get_member(user.id)
        if member.status not in [ChatMember.ADMINISTRATOR, ChatMember.OWNER]:
            await update.message.reply_text("⛔ Только администраторы могут использовать эту команду.")
            return
    except Exception as e:
        logger.error(f"Ошибка проверки прав: {e}")
        await update.message.reply_text("❌ Не удалось проверить ваши права.")
        return

    target_user_id = None
    if update.message.reply_to_message:
        target_user_id = update.message.reply_to_message.from_user.id
        logger.info(f"Целевой пользователь определён из реплая: {target_user_id}")
    else:
        args = context.args
        if not args:
            await update.message.reply_text("Укажите пользователя (ID или @username) или ответьте на его сообщение.")
            return
        arg = args[0]
        if arg.startswith('@'):
            try:
                chat_member = await chat.get_member(arg)
                target_user_id = chat_member.user.id
                logger.info(f"Целевой пользователь найден по username: {target_user_id}")
            except Exception as e:
                logger.error(f"Не найден пользователь {arg}: {e}")
                await update.message.reply_text("Не удалось найти пользователя с таким username в этой группе.")
                return
        else:
            try:
                target_user_id = int(arg)
                logger.info(f"Целевой пользователь найден по ID: {target_user_id}")
            except ValueError:
                await update.message.reply_text("Некорректный ID. Введите число или @username.")
                return

    if target_user_id is None:
        await update.message.reply_text("Не удалось определить пользователя.")
        return

    remove_ping_user(chat.id, target_user_id)
    logger.info(f"Пользователь {target_user_id} удалён из пингов администратором {user.id} в группе {chat.id}")
    await update.message.reply_text(f"✅ Пользователь удалён из списка упоминаний.")

async def listpings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    logger.info(f"Команда /listpings от {update.effective_user.id} в чате {chat.id}")

    if chat.type not in ["group", "supergroup"]:
        await update.message.reply_text("⚠️ Эта команда работает только в группах.")
        return

    pings = get_ping_users(chat.id)
    if not pings:
        await update.message.reply_text("📭 Список пользователей для упоминаний пуст.")
        return

    text = "📋 Список пользователей для упоминаний:\n"
    for ping in pings:
        username = ping['username'] or str(ping['user_id'])
        text += f"- @{username} (ID: {ping['user_id']})\n"
    await update.message.reply_text(text)

async def test(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"Команда /test от {update.effective_user.id} в чате {update.effective_chat.id}")
    await update.message.reply_text("🔄 Отправляю тестовое сообщение в группу...")
    await send_notification("🧪 Это тестовое сообщение от бота. Если вы его видите – всё работает!")
    await update.message.reply_text("✅ Тестовое сообщение отправлено (если группа и тема установлены).")

def register_handlers(app: Application):
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("setgroup", setgroup))
    app.add_handler(CommandHandler("addping", addping))
    app.add_handler(CommandHandler("removeping", removeping))
    app.add_handler(CommandHandler("listpings", listpings))
    app.add_handler(CommandHandler("test", test))

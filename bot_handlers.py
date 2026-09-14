import logging
from datetime import datetime
from telegram import Update, ChatMember, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from config import GROUP_CHAT_ID, GROUP_ID_FILE, TOPIC_ID_FILE, SECTION_NAMES, ALLOWED_USERS
from database import (
    add_ping_user, remove_ping_user, get_ping_users,
    get_all_topics, get_all_open_topics, mark_reminder_sent,
    update_topic_closed_status, reset_reminder,
    save_topic_closure, get_topic_closure, get_top_closers_for_month
)
from utils import send_notification, is_topic_closed_on_page, send_personal_reminder, format_moscow_time

logger = logging.getLogger(__name__)

PAGE_SIZE = 5
MONTH_NAMES = ["Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
               "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"]

def is_private_chat_allowed(user_id: int) -> bool:
    return user_id in ALLOWED_USERS

async def check_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    user_id = update.effective_user.id
    chat = update.effective_chat
    chat_type = chat.type
    if chat_type == "private":
        return is_private_chat_allowed(user_id)
    else:
        try:
            member = await chat.get_member(user_id)
            return member.status in [ChatMember.ADMINISTRATOR, ChatMember.OWNER]
        except Exception:
            return False

async def send_unauthorized(update: Update):
    if update.effective_chat.type == "private":
        await update.message.reply_html("⛔ У вас нет доступа к этой команде в ЛС.")
    else:
        await update.message.reply_html("⛔ Только администраторы могут использовать эту команду.")

# ---------- Команды ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat_type = update.effective_chat.type
    logger.info(f"/start от {user_id} в {chat_type}")

    if chat_type == "private" and not is_private_chat_allowed(user_id):
        await update.message.reply_html("⛔ У вас нет доступа к боту в личных сообщениях.")
        return

    await update.message.reply_html(
        "👋 Я бот для отслеживания новых тем на форуме VimeWorld.\n\n"
        "<b>Команды для администраторов:</b>\n"
        "/addping – добавить пользователя (реплай, ID или @username)\n"
        "/removeping – удалить пользователя\n"
        "/listpings – список пользователей для упоминаний\n"
        "/test – отправить тестовое уведомление (имитация новой темы)\n"
        "/forceremind – принудительно отправить напоминания (с проверкой закрытости)\n"
        "/topclosers – топ закрывающих тем за месяц (YYYY-MM)"
    )

async def setgroup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat = update.effective_chat
    chat_type = chat.type
    logger.info(f"/setgroup от {user_id} в {chat_type}")

    if chat_type == "private":
        await update.message.reply_html("⚠️ Эта команда работает только в группах.")
        return

    if not await check_admin(update, context):
        await send_unauthorized(update)
        return

    topic_id = update.effective_message.message_thread_id
    try:
        member = await chat.get_member(user_id)
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
    user_id = update.effective_user.id
    chat = update.effective_chat
    chat_type = chat.type
    logger.info(f"/addping от {user_id} в {chat_type}")

    if chat_type == "private":
        await update.message.reply_html("⚠️ Эта команда работает только в группах.")
        return

    if not await check_admin(update, context):
        await send_unauthorized(update)
        return

    target_user_id = None
    target_username = None

    if update.message.reply_to_message:
        target_user_id = update.message.reply_to_message.from_user.id
        target_username = update.message.reply_to_message.from_user.username
    elif context.args:
        arg = context.args[0]
        if arg.startswith('@'):
            target_username = arg[1:]
            target_user_id = None
        else:
            try:
                target_user_id = int(arg)
                try:
                    chat_member = await chat.get_member(target_user_id)
                    target_username = chat_member.user.username
                except:
                    target_username = None
            except ValueError:
                await update.message.reply_html("❌ Некорректный ID.")
                return
    else:
        await update.message.reply_html("❌ Укажите пользователя (ID или @username) или ответьте на его сообщение.")
        return

    add_ping_user(chat.id, target_user_id, target_username, added_by=user_id)
    await update.message.reply_html(f"✅ Пользователь @{target_username or target_user_id} добавлен.")

async def removeping(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat = update.effective_chat
    chat_type = chat.type
    logger.info(f"/removeping от {user_id} в {chat_type}")

    if chat_type == "private":
        await update.message.reply_html("⚠️ Эта команда работает только в группах.")
        return

    if not await check_admin(update, context):
        await send_unauthorized(update)
        return

    target_user_id = None
    target_username = None
    if update.message.reply_to_message:
        target_user_id = update.message.reply_to_message.from_user.id
        target_username = update.message.reply_to_message.from_user.username
    elif context.args:
        arg = context.args[0]
        if arg.startswith('@'):
            target_username = arg[1:]
        else:
            try:
                target_user_id = int(arg)
            except ValueError:
                await update.message.reply_html("❌ Некорректный ID.")
                return
    else:
        await update.message.reply_html("❌ Укажите пользователя (ID или @username) или ответьте на его сообщение.")
        return

    if target_user_id is not None:
        remove_ping_user(chat.id, user_id=target_user_id)
    elif target_username is not None:
        remove_ping_user(chat.id, username=target_username)
    else:
        await update.message.reply_html("❌ Не удалось определить пользователя.")
        return

    await update.message.reply_html("✅ Пользователь удалён.")

async def listpings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat = update.effective_chat
    chat_type = chat.type
    logger.info(f"/listpings от {user_id} в {chat_type}")

    if chat_type == "private":
        await update.message.reply_html("⚠️ Эта команда работает только в группах.")
        return

    if not await check_admin(update, context):
        await send_unauthorized(update)
        return

    pings = get_ping_users(chat.id)
    if not pings:
        await update.message.reply_html("📭 Список пуст.")
        return

    text = "📋 Список пользователей для упоминаний:\n"
    for ping in pings:
        if ping['user_id']:
            username = ping['username'] or str(ping['user_id'])
            text += f"- @{username} (ID: {ping['user_id']})\n"
        else:
            text += f"- @{ping['username']}\n"
    await update.message.reply_html(text)

async def test(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat_type = update.effective_chat.type
    logger.info(f"/test от {user_id} в {chat_type}")

    if chat_type == "private":
        if not is_private_chat_allowed(user_id):
            await update.message.reply_html("⛔ У вас нет доступа к этой команде в ЛС.")
            return
    else:
        if not await check_admin(update, context):
            await send_unauthorized(update)
            return

    test_topic_id = f"test_{user_id}_{int(datetime.utcnow().timestamp())}"
    current_time = format_moscow_time()
    msg = (
        f"🆕 <b>Тестовое сообщение</b>\n\n"
        f"📌 <b>Тема:</b> test\n"
        f"👤 <b>Автор:</b> test\n"
        f"🕒 <b>Время:</b> {current_time}\n"
        f"🔗 <a href='https://forum.vimeworld.com/'>Ссылка на форум</a>"
    )
    await send_notification(msg, topic_id=test_topic_id)
    await update.message.reply_html("✅ Тестовое уведомление отправлено.")

async def forceremind(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat = update.effective_chat
    chat_type = chat.type
    logger.info(f"/forceremind от {user_id} в {chat_type}")

    if chat_type == "private":
        if not is_private_chat_allowed(user_id):
            await update.message.reply_html("⛔ У вас нет доступа к этой команде в ЛС.")
            return
    else:
        if not await check_admin(update, context):
            await send_unauthorized(update)
            return

    try:
        topics = get_all_open_topics()
        if not topics:
            await update.message.reply_html("📭 Нет открытых тем для напоминания.")
            return
        sent_count = 0
        for topic in topics:
            topic_id, section_key, title, author, url = topic
            is_closed_now = await is_topic_closed_on_page(url)
            if is_closed_now:
                update_topic_closed_status(topic_id, is_closed=True)
                continue
            section_name = SECTION_NAMES.get(section_key, section_key)
            current_time = format_moscow_time()
            msg = f"⏰ <b>Есть не закрытая тема</b> в разделе <i>{section_name}</i>!\n\n" \
                  f"<b>Название:</b> {title}\n" \
                  f"<b>Автор:</b> {author}\n" \
                  f"🕒 <b>Время:</b> {current_time}\n" \
                  f"<a href='{url}'>Ссылка</a>"
            await send_notification(msg)
            reset_reminder(topic_id)
            sent_count += 1
        await update.message.reply_html(f"✅ Отправлено напоминаний: {sent_count}")
    except Exception as e:
        logger.error(f"Ошибка в /forceremind: {e}", exc_info=True)
        await update.message.reply_html(f"❌ Ошибка: {e}")

async def showdb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat = update.effective_chat
    chat_type = chat.type
    logger.info(f"/showdb от {user_id} в {chat_type}")

    if chat_type == "private":
        if not is_private_chat_allowed(user_id):
            await update.message.reply_html("⛔ У вас нет доступа к этой команде в ЛС.")
            return
    else:
        if not await check_admin(update, context):
            await send_unauthorized(update)
            return

    try:
        rows = get_all_topics()
        if not rows:
            await update.message.reply_html("📭 База данных пуста.")
            return
        text = "📋 <b>Темы в БД:</b>\n\n"
        for row in rows[:20]:
            text += f"ID: <code>{row['topic_id']}</code>\n"
            text += f"Название: {row['title']}\n"
            text += f"Напомнено: {row['reminder_sent']}, Закрыта: {row['is_closed']}\n"
            text += "---\n"
        if len(rows) > 20:
            text += f"... и ещё {len(rows)-20} тем"
        await update.message.reply_html(text)
    except Exception as e:
        logger.error(f"Ошибка в /showdb: {e}", exc_info=True)
        await update.message.reply_html(f"❌ Ошибка: {e}")

# ---------- Обработчик кнопки "Закрою" ----------
async def close_topic_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = query.from_user
    data = query.data
    topic_id = data.split("_")[2]

    logger.info(f"Нажата кнопка закрытия для темы {topic_id} пользователем {user.id}")

    existing = get_topic_closure(topic_id)
    if existing:
        await query.answer(f"❌ Тема уже закрыта пользователем {existing[0]}", show_alert=True)
        return

    save_topic_closure(topic_id, user.username or str(user.id), user_id=user.id, closed_at=datetime.utcnow())
    await query.edit_message_reply_markup(reply_markup=None)
    await query.answer(f"✅ Тема закрыта пользователем @{user.username or user.id}", show_alert=True)

    await context.bot.send_message(
        chat_id=query.message.chat_id,
        text=f"🔒 Тему забрал @{user.username or user.id}",
        reply_to_message_id=query.message.message_id,
        message_thread_id=query.message.message_thread_id
    )

# ---------- Команда /topclosers ----------
async def topclosers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat = update.effective_chat
    chat_type = chat.type
    logger.info(f"/topclosers от {user_id} в {chat_type}")

    if chat_type == "private":
        if not is_private_chat_allowed(user_id):
            await update.message.reply_html("⛔ У вас нет доступа к этой команде в ЛС.")
            return
    else:
        if not await check_admin(update, context):
            await send_unauthorized(update)
            return

    now = datetime.utcnow()
    year = now.year
    month = now.month

    if context.args:
        arg = context.args[0]
        try:
            parts = arg.strip().split('-')
            if len(parts) == 2:
                year = int(parts[0])
                month = int(parts[1])
            else:
                raise ValueError
        except:
            await update.message.reply_html("❌ Неверный формат. Используйте: /topclosers YYYY-MM")
            return

    if month < 1 or month > 12:
        await update.message.reply_html("❌ Месяц должен быть от 1 до 12.")
        return

    month_name = MONTH_NAMES[month-1]
    top = get_top_closers_for_month(year, month)

    if not top:
        await update.message.reply_html(f"📭 Нет данных о закрытых темах за {month_name} {year}.")
        return

    text = f"🏆 <b>Топ закрывающих за {month_name} {year}</b>\n\n"
    for idx, row in enumerate(top, 1):
        closed_by = row['closed_by'] if row['closed_by'] else "Неизвестный"
        user_id = row['user_id']
        count = row['count']
        from html import escape
        safe_name = escape(closed_by)
        text += f"{idx}. <a href=\"tg://user?id={user_id}\">{safe_name}</a> (<code>{user_id}</code>) — {count} тем(-а)\n"

    await update.message.reply_html(text)

def register_handlers(app: Application):
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("setgroup", setgroup))
    app.add_handler(CommandHandler("addping", addping))
    app.add_handler(CommandHandler("removeping", removeping))
    app.add_handler(CommandHandler("listpings", listpings))
    app.add_handler(CommandHandler("test", test))
    app.add_handler(CommandHandler("forceremind", forceremind))
    app.add_handler(CommandHandler("showdb", showdb))
    app.add_handler(CommandHandler("topclosers", topclosers))
    app.add_handler(CallbackQueryHandler(close_topic_callback, pattern="^close_topic_"))

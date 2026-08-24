from telegram import Update, ChatMember
from telegram.ext import Application, CommandHandler, ContextTypes
from config import GROUP_CHAT_ID
from database import add_ping_user, remove_ping_user, get_ping_users
import os

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Я бот для отслеживания новых тем на форуме VimeWorld.\n\n"
        "Команды для администраторов:\n"
        "/setgroup – установить текущую группу для уведомлений\n"
        "/addping – добавить пользователя для упоминания (через реплай, ID или @username)\n"
        "/removeping – удалить пользователя\n"
        "/listpings – показать список пользователей для упоминаний"
    )

async def setgroup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user

    if chat.type not in ["group", "supergroup"]:
        await update.message.reply_text("⚠️ Эта команда работает только в группах.")
        return

    try:
        member = await chat.get_member(user.id)
        if member.status not in [ChatMember.ADMINISTRATOR, ChatMember.OWNER]:
            await update.message.reply_text("⛔ Только администраторы группы могут использовать эту команду.")
            return
    except Exception:
        await update.message.reply_text("❌ Не удалось проверить ваши права.")
        return

    with open("group_id.txt", "w") as f:
        f.write(str(chat.id))

    global GROUP_CHAT_ID
    GROUP_CHAT_ID = chat.id
    import config
    config.GROUP_CHAT_ID = chat.id

    await update.message.reply_text(f"✅ Группа установлена для получения уведомлений (ID: {chat.id})")

async def addping(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user

    if chat.type not in ["group", "supergroup"]:
        await update.message.reply_text("⚠️ Эта команда работает только в группах.")
        return

    try:
        member = await chat.get_member(user.id)
        if member.status not in [ChatMember.ADMINISTRATOR, ChatMember.OWNER]:
            await update.message.reply_text("⛔ Только администраторы могут использовать эту команду.")
            return
    except Exception:
        await update.message.reply_text("❌ Не удалось проверить ваши права.")
        return

    target_user_id = None
    target_username = None

    if update.message.reply_to_message:
        target_user_id = update.message.reply_to_message.from_user.id
        target_username = update.message.reply_to_message.from_user.username
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
            except Exception:
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
            except ValueError:
                await update.message.reply_text("Некорректный ID. Введите число или @username.")
                return

    if target_user_id is None:
        await update.message.reply_text("Не удалось определить пользователя.")
        return

    add_ping_user(chat.id, target_user_id, target_username, added_by=user.id)
    await update.message.reply_text(f"✅ Пользователь {target_username or target_user_id} добавлен в список упоминаний.")

async def removeping(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user

    if chat.type not in ["group", "supergroup"]:
        await update.message.reply_text("⚠️ Эта команда работает только в группах.")
        return

    try:
        member = await chat.get_member(user.id)
        if member.status not in [ChatMember.ADMINISTRATOR, ChatMember.OWNER]:
            await update.message.reply_text("⛔ Только администраторы могут использовать эту команду.")
            return
    except Exception:
        await update.message.reply_text("❌ Не удалось проверить ваши права.")
        return

    target_user_id = None
    if update.message.reply_to_message:
        target_user_id = update.message.reply_to_message.from_user.id
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
            except Exception:
                await update.message.reply_text("Не удалось найти пользователя с таким username в этой группе.")
                return
        else:
            try:
                target_user_id = int(arg)
            except ValueError:
                await update.message.reply_text("Некорректный ID. Введите число или @username.")
                return

    if target_user_id is None:
        await update.message.reply_text("Не удалось определить пользователя.")
        return

    remove_ping_user(chat.id, target_user_id)
    await update.message.reply_text(f"✅ Пользователь удалён из списка упоминаний.")

async def listpings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
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

def register_handlers(app: Application):
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("setgroup", setgroup))
    app.add_handler(CommandHandler("addping", addping))
    app.add_handler(CommandHandler("removeping", removeping))
    app.add_handler(CommandHandler("listpings", listpings))

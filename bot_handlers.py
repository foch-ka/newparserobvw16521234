from telegram import Update, ChatMember
from telegram.ext import Application, CommandHandler, ContextTypes
from config import GROUP_CHAT_ID
import os

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Я бот для отслеживания новых тем на форуме VimeWorld.\n"
        "Все уведомления отправляются в эту группу.\n\n"
        "Команды:\n"
        "/setgroup – установить текущую группу для уведомлений (только для админов)"
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

    # Сохраняем ID группы в файл
    with open("group_id.txt", "w") as f:
        f.write(str(chat.id))
    
    # Обновляем глобальную переменную (чтобы сразу начало работать)
    global GROUP_CHAT_ID
    GROUP_CHAT_ID = chat.id
    # Также обновляем в модуле config (чтобы другие функции видели)
    import config
    config.GROUP_CHAT_ID = chat.id

    await update.message.reply_text(f"✅ Группа установлена для получения уведомлений (ID: {chat.id})")

def register_handlers(app: Application):
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("setgroup", setgroup))

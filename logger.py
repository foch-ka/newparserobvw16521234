import logging
import sys
from logging.handlers import RotatingFileHandler

def setup_logger():
    # Создаём логгер
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    # Формат сообщений
    formatter = logging.Formatter(
        '[%(asctime)s] %(levelname)s [%(name)s:%(lineno)d] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Вывод в консоль (для BotHost будет видно в логах)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # Вывод в файл с ротацией (максимум 5 файлов по 5 МБ)
    file_handler = RotatingFileHandler(
        'bot.log', maxBytes=5*1024*1024, backupCount=5, encoding='utf-8'
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger

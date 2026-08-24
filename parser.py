import logging
import aiohttp
from bs4 import BeautifulSoup
from config import FORUM_URLS, SECTION_NAMES, HEADERS
from database import (
    get_last_seen, update_last_seen,
    add_topic_for_reminder, topic_exists
)
from utils import send_notification, is_topic_closed_on_page, extract_topic_id_from_url

logger = logging.getLogger(__name__)

async def parse_section(section_key):
    url = FORUM_URLS.get(section_key)
    if not url:
        logger.warning(f"Нет URL для раздела {section_key}")
        return

    logger.info(f"Начинаем парсинг раздела {section_key}, URL: {url}")
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=HEADERS, timeout=15) as resp:
                html = await resp.text()
                logger.info(f"Получен HTML для {section_key}, длина: {len(html)} символов")
    except Exception as e:
        logger.error(f"Ошибка при запросе к {url}: {e}", exc_info=True)
        return

    soup = BeautifulSoup(html, "html.parser")
    last_topic_id = get_last_seen(section_key)
    logger.info(f"Последний известный ID для {section_key}: {last_topic_id}")

    # Поиск тем – пробуем разные селекторы
    topic_items = soup.select("li.ipsDataItem")
    if not topic_items:
        topic_items = soup.select("div.ipsDataItem")
    if not topic_items:
        topic_items = soup.select("[class*='ipsDataItem']")
    logger.info(f"Найдено элементов тем: {len(topic_items)}")

    if not topic_items:
        logger.warning(f"Не удалось найти темы в разделе {section_key}. Проверьте селекторы.")
        return

    new_topics_found = False
    for idx, item in enumerate(topic_items):
        title_tag = item.select_one("a.ipsDataItem_title")
        if not title_tag:
            logger.debug(f"Элемент {idx} не содержит заголовка, пропускаем")
            continue
        topic_url = title_tag.get("href")
        if not topic_url.startswith("http"):
            topic_url = "https://forum.vimeworld.com" + topic_url
        topic_id = extract_topic_id_from_url(topic_url)
        if not topic_id:
            logger.debug(f"Не удалось извлечь ID из URL: {topic_url}")
            continue
        if last_topic_id and topic_id == last_topic_id:
            logger.info(f"Достигнут последний известный ID {last_topic_id}, прекращаем")
            break
        if topic_exists(topic_id):
            logger.debug(f"Тема {topic_id} уже существует в БД, пропускаем")
            continue

        title = title_tag.text.strip()
        author_tag = item.select_one("a.ipsDataItem_author")
        author = author_tag.text.strip() if author_tag else "Неизвестен"

        lock_icon = item.select_one("span.ipsDataItem_icon .fa-lock")
        is_closed = lock_icon is not None
        if not is_closed:
            if "ipsDataItem_closed" in item.get("class", []):
                is_closed = True

        logger.info(f"Новая тема: '{title}', автор {author}, ID {topic_id}, закрыта: {is_closed}")

        add_topic_for_reminder(topic_id, section_key, title, author, topic_url, is_closed)
        if not is_closed:
            section_name = SECTION_NAMES.get(section_key, section_key)
            message = f"🆕 **Новая тема** в разделе *{section_name}*\n\n" \
                      f"**Название:** {title}\n" \
                      f"**Автор:** {author}\n" \
                      f"**Ссылка:** {topic_url}"
            await send_notification(message)
            logger.info(f"[{section_key}] Отправлено уведомление о новой теме: {title}")
        else:
            logger.info(f"[{section_key}] Тема закрыта, уведомление не отправлено: {title}")
        new_topics_found = True

    if new_topics_found and topic_items:
        first_topic_url = topic_items[0].select_one("a.ipsDataItem_title").get("href")
        if first_topic_url:
            first_id = extract_topic_id_from_url(first_topic_url)
            if first_id:
                update_last_seen(section_key, first_id)
                logger.info(f"Обновлён last_seen для {section_key}: {first_id}")
    else:
        logger.info(f"Новых тем в разделе {section_key} не найдено.")

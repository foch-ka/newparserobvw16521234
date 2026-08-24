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

    # Поиск элементов тем
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
    all_topic_ids = []

    for idx, item in enumerate(topic_items):
        title_tag = item.select_one("a.ipsDataItem_title")
        if not title_tag:
            logger.debug(f"Элемент {idx} не содержит заголовка, пропускаем")
            continue

        topic_url = title_tag.get("href")
        if not topic_url:
            logger.debug(f"Элемент {idx} не содержит ссылки")
            continue

        if not topic_url.startswith("http"):
            topic_url = "https://forum.vimeworld.com" + topic_url

        topic_id = extract_topic_id_from_url(topic_url)
        title = title_tag.text.strip()

        logger.info(f"[{idx}] Тема: '{title}', URL: {topic_url}, ID: {topic_id}")

        if not topic_id:
            logger.warning(f"[{idx}] НЕ УДАЛОСЬ извлечь ID из URL: {topic_url}")
            continue

        all_topic_ids.append(topic_id)

        # Проверяем, есть ли тема уже в БД
        if topic_exists(topic_id):
            logger.info(f"[{idx}] Тема {topic_id} уже существует в БД, пропускаем")
            continue

        # Новая тема
        logger.info(f"[{idx}] 🆕 НОВАЯ ТЕМА: '{title}' (ID: {topic_id})")

        author_tag = item.select_one("a.ipsDataItem_author")
        author = author_tag.text.strip() if author_tag else "Неизвестен"

        # Проверка закрытости (по иконке или классу)
        lock_icon = item.select_one("span.ipsDataItem_icon .fa-lock")
        is_closed = lock_icon is not None
        if not is_closed:
            if "ipsDataItem_closed" in item.get("class", []):
                is_closed = True

        # Сохраняем в БД (даже если закрыта)
        add_topic_for_reminder(topic_id, section_key, title, author, topic_url, is_closed)

        if not is_closed:
            section_name = SECTION_NAMES.get(section_key, section_key)
            message = f"🆕 **Новая тема** в разделе *{section_name}*\n\n" \
                      f"**Название:** {title}\n" \
                      f"**Автор:** {author}\n" \
                      f"**Ссылка:** {topic_url}"
            await send_notification(message)
            logger.info(f"[{section_key}] ✅ Отправлено уведомление о новой теме: {title}")
        else:
            logger.info(f"[{section_key}] 🔒 Тема закрыта, уведомление не отправлено: {title}")

        new_topics_found = True

    # Если были новые темы – обновляем last_seen на ID первой темы на странице
    if new_topics_found and all_topic_ids:
        first_id = all_topic_ids[0]
        update_last_seen(section_key, first_id)
        logger.info(f"Обновлён last_seen для {section_key}: {first_id} (всего новых тем: {len(all_topic_ids)})")
    else:
        logger.info(f"Новых тем в разделе {section_key} не найдено.")

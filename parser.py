import logging
import aiohttp
import asyncio
from bs4 import BeautifulSoup
from config import FORUM_URLS, SECTION_NAMES, HEADERS
from database import (
    get_last_seen, update_last_seen,
    add_topic_for_reminder, topic_exists
)
from utils import send_notification, is_topic_closed_on_page

logger = logging.getLogger(__name__)

async def fetch_html(url):
    """Асинхронно получает HTML страницы."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=HEADERS, timeout=15) as resp:
                return await resp.text()
    except Exception as e:
        logger.error(f"Ошибка загрузки {url}: {e}")
        return None

def parse_topics(html, section_key):
    """
    Парсит темы из HTML (адаптировано из вашего скрипта).
    Возвращает список словарей с полями: id, title, link, author, time.
    """
    soup = BeautifulSoup(html, 'html.parser')
    topics = []

    # Ищем элементы с классом, содержащим ipsDataItem
    items = soup.find_all('li', class_='ipsDataItem')
    if not items:
        items = soup.find_all(class_=lambda c: c and 'ipsDataItem' in c)

    logger.info(f"Найдено элементов: {len(items)}")
    for item in items:
        # Пропускаем закреплённые
        if 'ipsDataItem_pinned' in item.get('class', []):
            continue

        # Заголовок
        title_tag = item.find('h4', class_='ipsDataItem_title')
        if not title_tag:
            title_tag = item.find('a', class_='ipsDataItem_title')
        if not title_tag:
            title_tag = item.find('a')
        if not title_tag:
            continue

        link_tag = title_tag if title_tag.name == 'a' else title_tag.find('a')
        if not link_tag:
            continue

        title = link_tag.get_text(strip=True)
        link = link_tag.get('href')
        if link and not link.startswith('http'):
            link = "https://forum.vimeworld.com" + link

        # Автор
        meta = item.find('div', class_='ipsDataItem_meta')
        author = "Неизвестный"
        if meta:
            a = meta.find('a')
            if a:
                author = a.get_text(strip=True)

        # Время
        time_tag = meta.find('time') if meta else None
        if time_tag:
            event_time = time_tag.get_text(strip=True)
        else:
            time_span = meta.find('span', class_='ipsType_light') if meta else None
            event_time = time_span.get_text(strip=True) if time_span else ""

        # ID темы – используем ссылку как уникальный идентификатор
        topic_id = link if link else title

        topics.append({
            'id': topic_id,
            'title': title,
            'link': link,
            'author': author,
            'time': event_time
        })

    logger.info(f"Распарсено тем: {len(topics)}")
    return topics

async def parse_section(section_key):
    """Основная функция парсинга раздела (асинхронная)."""
    url = FORUM_URLS.get(section_key)
    if not url:
        logger.warning(f"Нет URL для раздела {section_key}")
        return

    logger.info(f"Начинаем парсинг раздела {section_key}, URL: {url}")
    html = await fetch_html(url)
    if not html:
        return

    topics = parse_topics(html, section_key)
    if not topics:
        logger.info(f"Тем не найдено в разделе {section_key}")
        return

    last_topic_id = get_last_seen(section_key)
    logger.info(f"Последний известный ID для {section_key}: {last_topic_id}")

    new_topics_found = False
    all_topic_ids = []

    for t in topics:
        topic_id = t['id']
        all_topic_ids.append(topic_id)

        if topic_exists(topic_id):
            logger.debug(f"Тема {topic_id} уже существует в БД, пропускаем")
            continue

        # Новая тема
        logger.info(f"🆕 НОВАЯ ТЕМА: {t['title']} (ID: {topic_id})")
        title = t['title']
        author = t['author']
        link = t['link']
        time_str = t['time']

        # Проверка закрытости
        is_closed = await is_topic_closed_on_page(link)
        logger.info(f"Тема '{title}' закрыта: {is_closed}")

        add_topic_for_reminder(topic_id, section_key, title, author, link, is_closed)

        if not is_closed:
            section_name = SECTION_NAMES.get(section_key, section_key)
            message = (
                f"🆕 **Новая тема** в разделе *{section_name}*\n\n"
                f"📌 **Тема:** {title}\n"
                f"👤 **Автор:** {author}\n"
                f"🕒 **Время:** {time_str}\n"
                f"🔗 [Ссылка]({link})"
            )
            await send_notification(message)
            logger.info(f"✅ Отправлено уведомление о новой теме: {title}")
        else:
            logger.info(f"🔒 Тема закрыта, уведомление не отправлено")

        new_topics_found = True
        await asyncio.sleep(0.5)  # защита от перегрузки

    if new_topics_found and all_topic_ids:
        first_id = all_topic_ids[0]
        update_last_seen(section_key, first_id)
        logger.info(f"Обновлён last_seen для {section_key}: {first_id} (всего новых тем: {len(all_topic_ids)})")
    else:
        logger.info(f"Новых тем в разделе {section_key} не найдено.")

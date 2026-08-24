import logging
import aiohttp
import asyncio
import re
from bs4 import BeautifulSoup
from config import FORUM_URLS, SECTION_NAMES, HEADERS
from database import (
    get_last_seen, update_last_seen,
    add_topic_for_reminder, topic_exists
)
from utils import send_notification, is_topic_closed_on_page

logger = logging.getLogger(__name__)

async def fetch_html(url):
    try:
        async with aiohttp.ClientSession() as session:
            await session.get("https://forum.vimeworld.com", headers=HEADERS)
            async with session.get(url, headers=HEADERS, timeout=15) as resp:
                return await resp.text()
    except Exception as e:
        logger.error(f"Ошибка загрузки {url}: {e}")
        return None

def extract_numeric_id(url):
    """Извлекает числовой ID темы из URL вида /topic/123456-..."""
    match = re.search(r'/topic/(\d+)-', url)
    if match:
        return match.group(1)
    # Если ссылка не соответствует, пробуем найти число в конце
    match = re.search(r'/(\d+)(?:-|$)', url)
    if match:
        return match.group(1)
    return None

def parse_topics(html, section_key):
    soup = BeautifulSoup(html, 'html.parser')
    topics = []

    # Ищем элементы с классом, содержащим 'ipsDataItem'
    items = soup.find_all(class_=lambda c: c and 'ipsDataItem' in c)
    if not items:
        items = soup.find_all('li', class_=lambda c: c and 'dataItem' in c)

    logger.info(f"Найдено элементов: {len(items)}")

    for item in items:
        if 'ipsDataItem_pinned' in item.get('class', []):
            continue

        # Заголовок и ссылка
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

        # Извлекаем числовой ID – теперь строго
        topic_id = extract_numeric_id(link)
        if not topic_id:
            logger.warning(f"Не удалось извлечь ID из ссылки: {link}")
            continue

        # Автор – ищем в нескольких местах
        author = "Неизвестный"
        meta = item.find('div', class_='ipsDataItem_meta')
        if meta:
            # Ищем ссылку на автора
            author_tag = meta.find('a', class_=lambda c: c and ('author' in c or 'user' in c))
            if not author_tag:
                author_tag = meta.find('a')
            if author_tag:
                author = author_tag.get_text(strip=True)
            else:
                # Иногда автор в span
                author_span = meta.find('span', class_='ipsType_light')
                if author_span:
                    author = author_span.get_text(strip=True)

        # Время
        time_tag = meta.find('time') if meta else None
        if time_tag:
            event_time = time_tag.get_text(strip=True)
        else:
            time_span = meta.find('span', class_='ipsType_light') if meta else None
            event_time = time_span.get_text(strip=True) if time_span else ""

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
    url = FORUM_URLS.get(section_key)
    if not url:
        logger.warning(f"Нет URL для раздела {section_key}")
        return

    logger.info(f"Парсинг раздела {section_key}: {url}")
    html = await fetch_html(url)
    if not html:
        return

    topics = parse_topics(html, section_key)
    if not topics:
        logger.info(f"Тем не найдено в {section_key}")
        return

    last_topic_id = get_last_seen(section_key)
    logger.info(f"Последний ID для {section_key}: {last_topic_id}")

    new_topics_found = False
    all_ids = []

    for t in topics:
        topic_id = t['id']
        all_ids.append(topic_id)

        # Проверяем, есть ли уже в БД
        if topic_exists(topic_id):
            logger.debug(f"Тема {topic_id} уже есть, пропускаем")
            continue

        # Новая тема
        logger.info(f"🆕 НОВАЯ ТЕМА: {t['title']} (ID: {topic_id})")
        is_closed = await is_topic_closed_on_page(t['link'])
        add_topic_for_reminder(topic_id, section_key, t['title'], t['author'], t['link'], is_closed)

        if not is_closed:
            section_name = SECTION_NAMES.get(section_key, section_key)
            msg = (
                f"🆕 **Новая тема** в разделе *{section_name}*\n\n"
                f"📌 **Тема:** {t['title']}\n"
                f"👤 **Автор:** {t['author']}\n"
                f"🕒 **Время:** {t['time']}\n"
                f"🔗 [Ссылка]({t['link']})"
            )
            await send_notification(msg)
            logger.info(f"✅ Отправлено: {t['title']}")
        else:
            logger.info(f"🔒 Тема закрыта: {t['title']}")

        new_topics_found = True
        await asyncio.sleep(0.5)

    if new_topics_found and all_ids:
        first_id = all_ids[0]  # самая новая тема
        update_last_seen(section_key, first_id)
        logger.info(f"Обновлён last_seen для {section_key}: {first_id}")
    else:
        logger.info(f"Новых тем в {section_key} нет")

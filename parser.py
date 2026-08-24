import requests
from bs4 import BeautifulSoup
from config import FORUM_URLS, SECTION_NAMES, HEADERS
from database import (
    get_last_seen, update_last_seen, 
    add_topic_for_reminder, topic_exists
)
from utils import send_notification, is_topic_closed_on_page, extract_topic_id_from_url

def parse_section(section_key):
    url = FORUM_URLS.get(section_key)
    if not url:
        return

    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        response.raise_for_status()
    except Exception as e:
        print(f"Ошибка при запросе к {url}: {e}")
        return

    soup = BeautifulSoup(response.text, "html.parser")
    last_topic_id = get_last_seen(section_key)
    topic_items = soup.select("li.ipsDataItem")
    if not topic_items:
        topic_items = soup.select("div.ipsDataItem")
    if not topic_items:
        print(f"Не удалось найти темы в разделе {section_key}")
        return

    new_topics_found = False
    for item in topic_items:
        title_tag = item.select_one("a.ipsDataItem_title")
        if not title_tag:
            continue
        topic_url = title_tag.get("href")
        if not topic_url.startswith("http"):
            topic_url = "https://forum.vimeworld.com" + topic_url
        topic_id = extract_topic_id_from_url(topic_url)
        if not topic_id:
            continue
        if last_topic_id and topic_id == last_topic_id:
            break
        if topic_exists(topic_id):
            continue
        title = title_tag.text.strip()
        author_tag = item.select_one("a.ipsDataItem_author")
        author = author_tag.text.strip() if author_tag else "Неизвестен"
        lock_icon = item.select_one("span.ipsDataItem_icon .fa-lock")
        is_closed = lock_icon is not None
        if not is_closed:
            if "ipsDataItem_closed" in item.get("class", []):
                is_closed = True

        add_topic_for_reminder(topic_id, section_key, title, author, topic_url, is_closed)
        if not is_closed:
            section_name = SECTION_NAMES.get(section_key, section_key)
            message = f"🆕 **Новая тема** в разделе *{section_name}*\n\n" \
                      f"**Название:** {title}\n" \
                      f"**Автор:** {author}\n" \
                      f"**Ссылка:** {topic_url}"
            send_notification(message)
            print(f"[{section_key}] Новая открытая тема: {title}")
        else:
            print(f"[{section_key}] Новая тема, но закрыта: {title}")
        new_topics_found = True

    if new_topics_found and topic_items:
        first_topic_url = topic_items[0].select_one("a.ipsDataItem_title").get("href")
        if first_topic_url:
            first_id = extract_topic_id_from_url(first_topic_url)
            if first_id:
                update_last_seen(section_key, first_id)

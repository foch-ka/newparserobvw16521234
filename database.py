import sqlite3
from datetime import datetime, timedelta
from config import DATABASE
import hashlib
import logging

logger = logging.getLogger(__name__)

def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS last_seen (
                    section_key TEXT PRIMARY KEY,
                    last_topic_id TEXT,
                    last_topic_time TIMESTAMP
                )''')
    c.execute('''CREATE TABLE IF NOT EXISTS pending_reminders (
                    topic_id TEXT PRIMARY KEY,
                    section_key TEXT,
                    title TEXT,
                    author TEXT,
                    url TEXT,
                    first_notified TIMESTAMP,
                    reminder_sent BOOLEAN DEFAULT 0,
                    is_closed BOOLEAN DEFAULT 0
                )''')
    c.execute('''CREATE TABLE IF NOT EXISTS group_pings (
                    chat_id INTEGER,
                    user_id INTEGER,
                    username TEXT,
                    added_by INTEGER,
                    added_at TIMESTAMP,
                    PRIMARY KEY (chat_id, user_id)
                )''')
    c.execute('''CREATE TABLE IF NOT EXISTS topic_closures (
                    topic_id TEXT PRIMARY KEY,
                    closed_by TEXT,
                    closed_at TIMESTAMP,
                    assigned_user_id INTEGER
                )''')
    try:
        c.execute("ALTER TABLE topic_closures ADD COLUMN assigned_user_id INTEGER")
    except sqlite3.OperationalError:
        pass
    conn.commit()
    conn.close()

def get_last_seen(section_key):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT last_topic_id FROM last_seen WHERE section_key = ?", (section_key,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else None

def update_last_seen(section_key, topic_id):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("REPLACE INTO last_seen (section_key, last_topic_id, last_topic_time) VALUES (?, ?, ?)",
              (section_key, topic_id, datetime.utcnow()))
    conn.commit()
    conn.close()

def add_topic_for_reminder(topic_id, section_key, title, author, url, is_closed=False):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('''INSERT OR IGNORE INTO pending_reminders 
                 (topic_id, section_key, title, author, url, first_notified, reminder_sent, is_closed)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
              (topic_id, section_key, title, author, url, datetime.utcnow(), 0, 1 if is_closed else 0))
    conn.commit()
    conn.close()

def update_topic_closed_status(topic_id, is_closed):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("UPDATE pending_reminders SET is_closed = ? WHERE topic_id = ?", (1 if is_closed else 0, topic_id))
    conn.commit()
    conn.close()

def mark_reminder_sent(topic_id):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("UPDATE pending_reminders SET reminder_sent = 1 WHERE topic_id = ?", (topic_id,))
    conn.commit()
    conn.close()

def reset_reminder(topic_id):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("UPDATE pending_reminders SET first_notified = ?, reminder_sent = 0 WHERE topic_id = ?",
              (datetime.utcnow(), topic_id))
    conn.commit()
    conn.close()

def get_topics_for_reminder():
    conn = get_db_connection()
    c = conn.cursor()
    threshold = datetime.utcnow() - timedelta(hours=24)
    c.execute('''SELECT topic_id, section_key, title, author, url, first_notified
                 FROM pending_reminders 
                 WHERE first_notified <= ? AND reminder_sent = 0 AND is_closed = 0''', (threshold,))
    rows = c.fetchall()
    conn.close()
    return rows

def get_all_open_topics():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('''SELECT topic_id, section_key, title, author, url 
                 FROM pending_reminders 
                 WHERE is_closed = 0''')
    rows = c.fetchall()
    conn.close()
    return rows

def topic_exists(topic_id):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT 1 FROM pending_reminders WHERE topic_id = ?", (topic_id,))
    row = c.fetchone()
    conn.close()
    return row is not None

def generate_virtual_id(chat_id, username):
    hash_obj = hashlib.md5(f"{chat_id}_{username}".encode())
    return -int(hash_obj.hexdigest()[:8], 16)

def add_ping_user(chat_id, user_id=None, username=None, added_by=None):
    logger.info(f"add_ping_user: chat_id={chat_id}, user_id={user_id}, username={username}")
    if user_id is None and username:
        user_id = generate_virtual_id(chat_id, username)
        logger.info(f"Сгенерирован виртуальный ID {user_id} для {username}")
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('''INSERT OR IGNORE INTO group_pings (chat_id, user_id, username, added_by, added_at)
                 VALUES (?, ?, ?, ?, ?)''',
              (chat_id, user_id, username, added_by, datetime.utcnow()))
    conn.commit()
    conn.close()

def remove_ping_user(chat_id, user_id=None, username=None):
    logger.info(f"remove_ping_user: chat_id={chat_id}, user_id={user_id}, username={username}")
    conn = get_db_connection()
    c = conn.cursor()
    if user_id is not None:
        c.execute("DELETE FROM group_pings WHERE chat_id = ? AND user_id = ?", (chat_id, user_id))
    elif username is not None:
        virtual_id = generate_virtual_id(chat_id, username)
        c.execute("DELETE FROM group_pings WHERE chat_id = ? AND user_id = ?", (chat_id, virtual_id))
        c.execute("DELETE FROM group_pings WHERE chat_id = ? AND username = ? AND user_id > 0", (chat_id, username))
    else:
        conn.close()
        return
    conn.commit()
    conn.close()

def get_ping_users(chat_id):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT user_id, username FROM group_pings WHERE chat_id = ?", (chat_id,))
    rows = c.fetchall()
    conn.close()
    return rows

def get_all_topics():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT topic_id, title, first_notified, reminder_sent, is_closed FROM pending_reminders")
    rows = c.fetchall()
    conn.close()
    return rows

def save_topic_closure(topic_id, closed_by, user_id=None, closed_at=None):
    if closed_at is None:
        closed_at = datetime.utcnow()
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('''INSERT OR REPLACE INTO topic_closures (topic_id, closed_by, closed_at, assigned_user_id)
                 VALUES (?, ?, ?, ?)''',
              (topic_id, closed_by, closed_at, user_id))
    conn.commit()
    conn.close()

def get_topic_closure(topic_id):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT closed_by, closed_at, assigned_user_id FROM topic_closures WHERE topic_id = ?", (topic_id,))
    row = c.fetchone()
    conn.close()
    return row if row else None

def get_top_closers_for_month(year, month):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('''SELECT assigned_user_id, closed_by, COUNT(*) as count 
                 FROM topic_closures 
                 WHERE strftime('%Y', closed_at) = ? AND strftime('%m', closed_at) = ?
                 GROUP BY assigned_user_id, closed_by''', (str(year), f"{month:02d}"))
    rows = c.fetchall()
    data = {}
    for row in rows:
        user_id = row['assigned_user_id']
        if user_id is None:
            continue
        username = row['closed_by']
        data[user_id] = {'username': username, 'count': row['count']}
    conn.close()
    result = []
    for user_id, info in data.items():
        if info['count'] > 0:
            result.append({'closed_by': info['username'], 'count': info['count'], 'user_id': user_id})
    result.sort(key=lambda x: x['count'], reverse=True)
    return result

import sqlite3
from datetime import datetime, timedelta
from config import DATABASE

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
              (section_key, topic_id, datetime.now()))
    conn.commit()
    conn.close()

def add_topic_for_reminder(topic_id, section_key, title, author, url, is_closed=False):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('''INSERT OR IGNORE INTO pending_reminders 
                 (topic_id, section_key, title, author, url, first_notified, reminder_sent, is_closed)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
              (topic_id, section_key, title, author, url, datetime.now(), 0, 1 if is_closed else 0))
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

def get_topics_for_reminder():
    """Используется в планировщике – только те, где прошло 24 часа."""
    conn = get_db_connection()
    c = conn.cursor()
    threshold = datetime.now() - timedelta(hours=24)
    c.execute('''SELECT topic_id, section_key, title, author, url 
                 FROM pending_reminders 
                 WHERE first_notified <= ? AND reminder_sent = 0 AND is_closed = 0''', (threshold,))
    rows = c.fetchall()
    conn.close()
    return rows

def get_all_pending_topics():
    """Используется в /forceremind – все темы, где reminder_sent=0 и is_closed=0, без учёта времени."""
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('''SELECT topic_id, section_key, title, author, url 
                 FROM pending_reminders 
                 WHERE reminder_sent = 0 AND is_closed = 0''')
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

def add_ping_user(chat_id, user_id, username=None, added_by=None):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('''INSERT OR IGNORE INTO group_pings (chat_id, user_id, username, added_by, added_at)
                 VALUES (?, ?, ?, ?, ?)''',
              (chat_id, user_id, username, added_by, datetime.now()))
    conn.commit()
    conn.close()

def remove_ping_user(chat_id, user_id):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("DELETE FROM group_pings WHERE chat_id = ? AND user_id = ?", (chat_id, user_id))
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

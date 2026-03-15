import sqlite3
import datetime
import os

from config import TXT_LOGS_FOLDER, MEDIA_FOLDER


# Adapters so Python datetime objects can be stored in SQLite
def _adapt_datetime(dt):
    return dt.isoformat()

def _convert_datetime(raw):
    return datetime.datetime.fromisoformat(raw.decode())

sqlite3.register_adapter(datetime.datetime, _adapt_datetime)
sqlite3.register_converter("datetime", _convert_datetime)

conn = sqlite3.connect('deleted_messages.db', detect_types=sqlite3.PARSE_DECLTYPES)
cursor = conn.cursor()

cursor.execute('DROP TABLE IF EXISTS deleted_messages')
cursor.execute('''
CREATE TABLE deleted_messages (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id      INTEGER,
    chat_name    TEXT,
    sender_id    INTEGER,
    sender_name  TEXT,
    message_text TEXT,
    message_date datetime,
    deleted_at   datetime,
    media_path   TEXT,
    media_type   TEXT,
    is_view_once BOOLEAN DEFAULT 0
)
''')
conn.commit()

os.makedirs(MEDIA_FOLDER, exist_ok=True)
os.makedirs(TXT_LOGS_FOLDER, exist_ok=True)

_ts          = datetime.datetime.now().strftime("%d.%m.%Y_%H-%M-%S")
txt_filepath = os.path.join(TXT_LOGS_FOLDER, f"deleted_messages_{_ts}.txt")

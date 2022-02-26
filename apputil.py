import sqlite3
import os

DB_PATH = 'ranger_db.db'

def create_conn():
    conn = None
    try:
        if os.path.exists(DB_PATH):
            conn = sqlite3.connect(DB_PATH)
            conn.cursor().execute('PRAGMA foreign_keys = ON')
            return conn
        new_db_file = open(DB_PATH, 'w')
        new_db_file.close()
        conn = sqlite3.connect(DB_PATH)
        conn.cursor().execute('PRAGMA foreign_keys = ON')
        return conn
    except Exception as e:
        print(e)
        if conn:
            conn.close()
        return None


def is_null_or_whitespace(text: str):
    if text is None:
        return True
    elif text.isspace():
        return True
    else:
        return False


def get_config_var(var_name: str, guild_id: int):
    db_conn = create_conn()
    db_cursor = db_conn.cursor()
    config_var = db_cursor.execute(f"""
        SELECT * FROM Configuration WHERE var_name = '{var_name}' AND guild_id = {guild_id}
    """).fetchone()
    db_cursor.close()
    db_conn.close()
    return config_var


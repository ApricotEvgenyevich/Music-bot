import sqlite3
import os


DB_PATH = 'database.db'


def init_db():
    """Инициализация базы данных"""
    if not os.path.exists(DB_PATH):
        print("Создание базы данных")    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor() 
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        telegram_id INTEGER UNIQUE NOT NULL,
        username TEXT
    )
    ''')


    cursor.execute('''
    CREATE TABLE IF NOT EXISTS tracks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        file_id TEXT NOT NULL,
        title TEXT NOT NULL,
        artist TEXT,
        duration INTEGER,
        added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id)
    )
    ''')
    
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS playlists (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id)
    )
    ''')
    
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS playlist_tracks (
        playlist_id INTEGER NOT NULL,
        track_id INTEGER NOT NULL,
        FOREIGN KEY (playlist_id) REFERENCES playlists(id),
        FOREIGN KEY (track_id) REFERENCES tracks(id),
        PRIMARY KEY (playlist_id, track_id)
    )
    ''')    
    conn.commit()
    conn.close()


def get_or_create_user(telegram_id, username=None):    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()    
    cursor.execute("SELECT id FROM users WHERE telegram_id = ?", (telegram_id,))
    result = cursor.fetchone()    
    if result:
        user_id = result[0]
    else:
        cursor.execute("INSERT INTO users (telegram_id, username) VALUES (?, ?)", (telegram_id, username))
        user_id = cursor.lastrowid    
    conn.commit()
    conn.close()
    return user_id


def add_track(user_id, file_id, title, artist=None, duration=None):    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()    
    cursor.execute("""
        INSERT INTO tracks (user_id, file_id, title, artist, duration)
        VALUES (?, ?, ?, ?, ?)
    """, (user_id, file_id, title, artist, duration))    
    track_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return track_id


def get_user_tracks(user_id, limit=20):    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()    
    cursor.execute("""
        SELECT id, title, artist, duration 
        FROM tracks 
        WHERE user_id = ?
        ORDER BY added_at DESC
        LIMIT ?
    """, (user_id, limit))    
    tracks = cursor.fetchall()
    conn.close()
    return tracks


def create_playlist(user_id, name):    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()    
    cursor.execute("""
        INSERT INTO playlists (user_id, name)
        VALUES (?, ?)
    """, (user_id, name))    
    playlist_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return playlist_id


def get_user_playlists(user_id):    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()    
    cursor.execute("""
        SELECT id, name 
        FROM playlists 
        WHERE user_id = ?
        ORDER BY created_at DESC
    """, (user_id,))    
    playlists = cursor.fetchall()
    conn.close()
    return playlists


def get_playlist_tracks(playlist_id):    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()    
    cursor.execute("""
        SELECT t.id, t.title, t.artist, t.duration
        FROM tracks t
        JOIN playlist_tracks pt ON t.id = pt.track_id
        WHERE pt.playlist_id = ?
        ORDER BY t.added_at DESC
    """, (playlist_id,))    
    tracks = cursor.fetchall()
    conn.close()
    return tracks

def get_track_by_id(track_id):    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()    
    cursor.execute("""
        SELECT id, user_id, file_id, title, artist, duration
        FROM tracks 
        WHERE id = ?
    """, (track_id,))    
    track = cursor.fetchone()
    conn.close()
    return track


def add_track_to_playlist(playlist_id, track_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()    
    try:
        cursor.execute("""
            INSERT INTO playlist_tracks (playlist_id, track_id)
            VALUES (?, ?)
        """, (playlist_id, track_id))
        conn.commit()
        return True
    except sqlite3.IntegrityError:        
        return False
    finally:
        conn.close()


def remove_track_from_playlist(playlist_id, track_id):    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()    
    cursor.execute("""
        DELETE FROM playlist_tracks 
        WHERE playlist_id = ? AND track_id = ?
    """, (playlist_id, track_id))    
    conn.commit()
    conn.close()


def is_track_in_playlist(playlist_id, track_id):    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()    
    cursor.execute("""
        SELECT 1 FROM playlist_tracks 
        WHERE playlist_id = ? AND track_id = ?
    """, (playlist_id, track_id))    
    result = cursor.fetchone()
    conn.close()
    return result is not None
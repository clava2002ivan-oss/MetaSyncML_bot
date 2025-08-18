# -*- coding: utf-8 -*-

import sqlite3
from datetime import datetime, timedelta
from config import DATABASE_NAME, ACTIVE_TIMEOUT_MINUTES

class Database:
    """Класс для работы с базой данных MLBB Team Finder."""
    
    def __init__(self):
        """Инициализирует подключение к базе данных."""
        self.db_name = DATABASE_NAME
        self.init_db()
    
    def init_db(self):
        """Инициализирует базу данных и создает таблицы, если их нет."""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        
        # Таблица для анкет пользователей
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS profiles (
            user_id INTEGER PRIMARY KEY,
            telegram_username TEXT,
            nickname TEXT,
            winrate INTEGER,
            line TEXT,
            rank TEXT,
            mythic_rank TEXT,
            goal TEXT,
            about TEXT,
            photo_id TEXT,
            last_active TIMESTAMP
        )''')
        
        # Таблица для лайков
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS likes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            liker_id INTEGER,
            liked_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (liker_id) REFERENCES profiles(user_id),
            FOREIGN KEY (liked_id) REFERENCES profiles(user_id)
        )''')
        
        # Индексы для улучшения производительности
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_last_active ON profiles(last_active)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_likes_liker ON likes(liker_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_likes_liked ON likes(liked_id)')
        
        conn.commit()
        conn.close()
    
    def user_exists(self, user_id):
        """Проверяет, есть ли анкета пользователя в базе."""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM profiles WHERE user_id = ?", (user_id,))
        exists = cursor.fetchone() is not None
        conn.close()
        return exists
    
    def update_last_active(self, user_id):
        """Обновляет время последней активности пользователя."""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        cursor.execute("UPDATE profiles SET last_active = ? WHERE user_id = ?", (datetime.now(), user_id))
        conn.commit()
        conn.close()
    
    def save_profile(self, user_id, data):
        """Сохраняет или обновляет профиль пользователя в базе данных."""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM profiles WHERE user_id = ?", (user_id,))
        exists = cursor.fetchone()
        
        if exists:
            cursor.execute('''
            UPDATE profiles SET telegram_username = ?, nickname = ?, winrate = ?, line = ?, rank = ?, mythic_rank = ?, goal = ?, about = ?, photo_id = ?, last_active = ? WHERE user_id = ?
            ''', (data.get('telegram_username'), data.get('nickname'), data.get('winrate'), data.get('line'), data.get('rank'), data.get('mythic_rank'), data.get('goal'), data.get('about'), data.get('photo_id'), datetime.now(), user_id))
        else:
            cursor.execute('''
            INSERT INTO profiles (user_id, telegram_username, nickname, winrate, line, rank, mythic_rank, goal, about, photo_id, last_active) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (user_id, data.get('telegram_username'), data.get('nickname'), data.get('winrate'), data.get('line'), data.get('rank'), data.get('mythic_rank'), data.get('goal'), data.get('about'), data.get('photo_id'), datetime.now()))
        
        conn.commit()
        conn.close()
    
    def get_profile(self, user_id):
        """Возвращает данные анкеты пользователя в виде словаря."""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM profiles WHERE user_id = ?", (user_id,))
        profile_data = cursor.fetchone()
        conn.close()
        
        if profile_data:
            keys = ["user_id", "telegram_username", "nickname", "winrate", "line", "rank", "mythic_rank", "goal", "about", "photo_id", "last_active"]
            return dict(zip(keys, profile_data))
        return None
    
    def delete_profile(self, user_id):
        """Удаляет анкету пользователя и все связанные лайки."""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM profiles WHERE user_id = ?", (user_id,))
        cursor.execute("DELETE FROM likes WHERE liker_id = ? OR liked_id = ?", (user_id, user_id))
        conn.commit()
        conn.close()
    
    def get_active_profiles(self, exclude_user_id):
        """Возвращает список активных пользователей, исключая указанного."""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        time_threshold = datetime.now() - timedelta(minutes=ACTIVE_TIMEOUT_MINUTES)
        cursor.execute("SELECT user_id FROM profiles WHERE user_id != ? AND last_active >= ?", (exclude_user_id, time_threshold))
        profiles_found = [row[0] for row in cursor.fetchall()]
        conn.close()
        return profiles_found
    
    def add_like(self, liker_id, liked_id):
        """Добавляет лайк от одного пользователя к другому."""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        
        # Проверяем, не лайкал ли уже
        cursor.execute("SELECT 1 FROM likes WHERE liker_id = ? AND liked_id = ?", (liker_id, liked_id))
        if cursor.fetchone() is not None:
            conn.close()
            return False  # Лайк уже существует
        
        cursor.execute("INSERT INTO likes (liker_id, liked_id) VALUES (?, ?)", (liker_id, liked_id))
        conn.commit()
        conn.close()
        return True
    
    def check_mutual_like(self, user1_id, user2_id):
        """Проверяет, есть ли взаимный лайк между двумя пользователями."""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM likes WHERE liker_id = ? AND liked_id = ?", (user1_id, user2_id))
        like1 = cursor.fetchone() is not None
        cursor.execute("SELECT 1 FROM likes WHERE liker_id = ? AND liked_id = ?", (user2_id, user1_id))
        like2 = cursor.fetchone() is not None
        conn.close()
        return like1 and like2
    
    def get_likes_for_user(self, user_id):
        """Возвращает список пользователей, которые лайкнули указанного пользователя, но не получили лайк в ответ."""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT l1.liker_id FROM likes l1 
            WHERE l1.liked_id = ? 
            AND NOT EXISTS (
                SELECT 1 FROM likes l2 
                WHERE l2.liker_id = ? AND l2.liked_id = l1.liker_id
            )
        ''', (user_id, user_id))
        profiles_found = [row[0] for row in cursor.fetchall()]
        conn.close()
        return profiles_found
    
    def get_user_stats(self, user_id):
        """Возвращает статистику пользователя."""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        
        # Количество лайков, которые поставил пользователь
        cursor.execute("SELECT COUNT(*) FROM likes WHERE liker_id = ?", (user_id,))
        likes_given = cursor.fetchone()[0]
        
        # Количество лайков, которые получил пользователь
        cursor.execute("SELECT COUNT(*) FROM likes WHERE liked_id = ?", (user_id,))
        likes_received = cursor.fetchone()[0]
        
        # Количество взаимных лайков (мэтчей)
        cursor.execute('''
            SELECT COUNT(*) FROM likes l1 
            WHERE l1.liker_id = ? 
            AND EXISTS (
                SELECT 1 FROM likes l2 
                WHERE l2.liker_id = l1.liked_id AND l2.liked_id = l1.liker_id
            )
        ''', (user_id,))
        matches = cursor.fetchone()[0]
        
        conn.close()
        
        return {
            'likes_given': likes_given,
            'likes_received': likes_received,
            'matches': matches
        }
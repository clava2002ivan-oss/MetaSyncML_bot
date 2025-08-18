# -*- coding: utf-8 -*-

# --- БИБЛИОТЕКИ ---
import telebot
from telebot import types
import sqlite3
import os
from datetime import datetime, timedelta
from config import get_token, DATABASE_NAME, ACTIVE_TIMEOUT_MINUTES, MAX_PROFILES_PER_SEARCH

# --- НАСТРОЙКИ И БЕЗОПАСНОСТЬ ---
TOKEN = get_token()

# --- ИНИЦИАЛИЗАЦИЯ БОТА И ДАННЫХ ---
bot = telebot.TeleBot(TOKEN)
# Словарь для временного хранения данных при регистрации анкеты
user_data = {}

# --- РАБОТА С БАЗОЙ ДАННЫХ (SQLite) ---

def init_db():
    """Инициализирует базу данных и создает таблицы, если их нет."""
    conn = sqlite3.connect(DATABASE_NAME)
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

def user_exists(user_id):
    """Проверяет, есть ли анкета пользователя в базе."""
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM profiles WHERE user_id = ?", (user_id,))
    exists = cursor.fetchone() is not None
    conn.close()
    return exists

def update_last_active(user_id):
    """Обновляет время последней активности пользователя."""
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute("UPDATE profiles SET last_active = ? WHERE user_id = ?", (datetime.now(), user_id))
    conn.commit()
    conn.close()

def save_profile(user_id, data):
    """Сохраняет или обновляет профиль пользователя в базе данных."""
    conn = sqlite3.connect(DATABASE_NAME)
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

def get_profile(user_id):
    """Возвращает данные анкеты пользователя в виде словаря."""
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM profiles WHERE user_id = ?", (user_id,))
    profile_data = cursor.fetchone()
    conn.close()
    if profile_data:
        keys = ["user_id", "telegram_username", "nickname", "winrate", "line", "rank", "mythic_rank", "goal", "about", "photo_id", "last_active"]
        return dict(zip(keys, profile_data))
    return None

def delete_profile(user_id):
    """Удаляет анкету пользователя и все связанные лайки."""
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM profiles WHERE user_id = ?", (user_id,))
    cursor.execute("DELETE FROM likes WHERE liker_id = ? OR liked_id = ?", (user_id, user_id))
    conn.commit()
    conn.close()

def get_active_profiles(exclude_user_id, limit=MAX_PROFILES_PER_SEARCH):
    """Получает список активных профилей для поиска."""
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    time_threshold = datetime.now() - timedelta(minutes=ACTIVE_TIMEOUT_MINUTES)
    cursor.execute("""
        SELECT user_id FROM profiles 
        WHERE user_id != ? AND last_active >= ? 
        ORDER BY last_active DESC 
        LIMIT ?
    """, (exclude_user_id, time_threshold, limit))
    profiles_found = [row[0] for row in cursor.fetchall()]
    conn.close()
    return profiles_found

def get_likes_for_user(user_id):
    """Получает список пользователей, которые лайкнули данного пользователя."""
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT l1.liker_id FROM likes l1 
        WHERE l1.liked_id = ? 
        AND NOT EXISTS (
            SELECT 1 FROM likes l2 
            WHERE l2.liker_id = ? AND l2.liked_id = l1.liker_id
        )
        ORDER BY l1.created_at DESC
    ''', (user_id, user_id))
    profiles_found = [row[0] for row in cursor.fetchall()]
    conn.close()
    return profiles_found

def add_like(liker_id, liked_id):
    """Добавляет лайк в базу данных."""
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM likes WHERE liker_id = ? AND liked_id = ?", (liker_id, liked_id))
    if cursor.fetchone() is None:
        cursor.execute("INSERT INTO likes (liker_id, liked_id) VALUES (?, ?)", (liker_id, liked_id))
        conn.commit()
        result = True
    else:
        result = False
    conn.close()
    return result

def check_mutual_like(user1_id, user2_id):
    """Проверяет, есть ли взаимный лайк между двумя пользователями."""
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM likes WHERE liker_id = ? AND liked_id = ?", (user1_id, user2_id))
    like1 = cursor.fetchone() is not None
    cursor.execute("SELECT 1 FROM likes WHERE liker_id = ? AND liked_id = ?", (user2_id, user1_id))
    like2 = cursor.fetchone() is not None
    conn.close()
    return like1 and like2

# --- КЛАВИАТУРЫ (ReplyKeyboardMarkup) ---

def create_start_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    markup.add(types.KeyboardButton("🔥 Начать"), types.KeyboardButton("ℹ️ О нас"))
    return markup

def create_fill_profile_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    markup.add(types.KeyboardButton("📝 Заполнить анкету"))
    return markup

def create_line_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    markup.row("Gold Line", "Rome", "Средняя линия")
    markup.row("Лес", "XP Line", "Везде")
    markup.add(types.KeyboardButton("⬅️ Назад"))
    return markup

def create_rank_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    markup.row("Воин", "Элита", "Мастер")
    markup.row("Грандмастер", "Эпик", "Легенда")
    markup.add("Мифический")
    markup.add(types.KeyboardButton("⬅️ Назад"))
    return markup

def create_mythic_rank_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    markup.row("Миф", "Мифическая честь")
    markup.row("Мифическая слава", "Мифический бессмертный")
    markup.add(types.KeyboardButton("⬅️ Назад"))
    return markup
    
def create_goal_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    markup.add("Поднять ранг", "Поиграть для удовольствия", "Найти постоянную команду")
    markup.add(types.KeyboardButton("⬅️ Назад"))
    return markup

def create_photo_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    markup.add(types.KeyboardButton("📷 Добавить фото"), types.KeyboardButton("➡️ Завершить"))
    return markup

def create_skip_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    markup.add(types.KeyboardButton("➡️ Далее"))
    return markup

def create_main_menu_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("🚀 Быстрый поиск", "⚙️ Поиск тиммейта")
    markup.row("👤 Моя анкета", "❤️ Понравился")
    markup.row("📊 Статистика")
    return markup

def create_my_profile_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    markup.add(types.KeyboardButton("✏️ Редактировать анкету"), types.KeyboardButton("🗑️ Удалить анкету"))
    markup.add(types.KeyboardButton("⬅️ В меню"))
    return markup

def create_confirm_delete_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    markup.add(types.KeyboardButton("Да, удалить"), types.KeyboardButton("Нет, отмена"))
    return markup

def create_search_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("❤️ Нравится", "👎 Следующий", "⏹️ Завершить поиск")
    return markup

def create_liked_by_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("❤️ Нравится в ответ", "👎 Пропустить", "⏹️ Вернуться в меню")
    return markup

# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---

def format_profile(profile_data):
    """Форматирует данные анкеты в красивый текст для вывода."""
    if not profile_data: return "Анкета не найдена."
    mythic_rank_str = f"\n🏅 Уровень мифа: {profile_data['mythic_rank']}" if profile_data.get('mythic_rank') else ""
    about_str = f"\n💬 О себе: {profile_data['about']}" if profile_data.get('about') else ""
    text = (f"👤 Ник: {profile_data['nickname']}\n"
            f"📊 Winrate: {profile_data['winrate']}%\n"
            f"⚔️ Линия: {profile_data['line']}\n"
            f"🏆 Ранг: {profile_data['rank']}{mythic_rank_str}\n"
            f"🎯 Цель: {profile_data['goal']}{about_str}")
    return text

def get_user_stats(user_id):
    """Получает статистику пользователя."""
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    
    # Количество лайков, которые поставил пользователь
    cursor.execute("SELECT COUNT(*) FROM likes WHERE liker_id = ?", (user_id,))
    likes_given = cursor.fetchone()[0]
    
    # Количество лайков, которые получил пользователь
    cursor.execute("SELECT COUNT(*) FROM likes WHERE liked_id = ?", (user_id,))
    likes_received = cursor.fetchone()[0]
    
    # Количество мэтчей
    cursor.execute("""
        SELECT COUNT(*) FROM likes l1 
        WHERE l1.liker_id = ? 
        AND EXISTS (SELECT 1 FROM likes l2 WHERE l2.liker_id = l1.liked_id AND l2.liked_id = l1.liker_id)
    """, (user_id,))
    matches = cursor.fetchone()[0]
    
    conn.close()
    
    return {
        'likes_given': likes_given,
        'likes_received': likes_received,
        'matches': matches
    }

# --- ОСНОВНЫЕ ОБРАБОТЧИКИ КОМАНД И СООБЩЕНИЙ ---

@bot.message_handler(commands=['start'])
def send_welcome(message):
    """Обработчик команды /start."""
    user_id = message.from_user.id
    if user_exists(user_id):
        update_last_active(user_id)
        bot.send_message(user_id, "С возвращением! Добро пожаловать в главное меню.", reply_markup=create_main_menu_keyboard())
    else:
        bot.send_message(message.chat.id, "👋 Привет! Хочешь найти тиммейтов для Mobile Legends?", reply_markup=create_start_keyboard())

@bot.message_handler(commands=['help'])
def send_help(message):
    """Обработчик команды /help."""
    help_text = """
🤖 **Помощь по использованию бота**

**Основные команды:**
/start - Начать работу с ботом
/help - Показать эту справку
/stats - Показать вашу статистику

**Функции бота:**
• Создание и редактирование анкет
• Поиск активных тиммейтов
• Система лайков и мэтчей
• Просмотр статистики

**Как использовать:**
1. Создайте анкету с информацией о себе
2. Используйте "Быстрый поиск" для поиска игроков
3. Лайкайте понравившихся игроков
4. При взаимном лайке получите мэтч!

**Поддержка:**
Если у вас есть вопросы, обратитесь к администратору.
    """
    bot.send_message(message.chat.id, help_text, parse_mode='Markdown')

@bot.message_handler(commands=['stats'])
def send_stats(message):
    """Обработчик команды /stats."""
    user_id = message.from_user.id
    if not user_exists(user_id):
        bot.send_message(user_id, "Сначала создайте анкету!", reply_markup=create_fill_profile_keyboard())
        return
    
    update_last_active(user_id)
    stats = get_user_stats(user_id)
    
    stats_text = f"""
📊 **Ваша статистика:**

❤️ Лайков поставлено: {stats['likes_given']}
💌 Лайков получено: {stats['likes_received']}
🎉 Мэтчей: {stats['matches']}

Продолжайте искать тиммейтов!
    """
    bot.send_message(user_id, stats_text, parse_mode='Markdown', reply_markup=create_main_menu_keyboard())

@bot.message_handler(func=lambda message: message.text == "⬅️ Назад")
def back_to_start(message):
    """Обработчик кнопки 'Назад' для отмены регистрации."""
    user_data.pop(message.from_user.id, None) 
    send_welcome(message)

# --- СЦЕНАРИЙ РЕГИСТРАЦИИ АНКЕТЫ ---

@bot.message_handler(func=lambda message: message.text in ["🔥 Начать", "ℹ️ О нас", "📝 Заполнить анкету"])
def handle_start_options(message):
    """Обрабатывает первые шаги пользователя."""
    user_id = message.from_user.id
    if message.text == "ℹ️ О нас":
        about_text = """
🎮 **О боте для поиска тиммейтов MLBB**

Этот бот создан для помощи игрокам Mobile Legends Bang Bang в поиске тиммейтов для совместной игры.

**Возможности:**
• Создание подробных анкет
• Поиск активных игроков
• Система лайков и мэтчей
• Удобный интерфейс

**Наша миссия:**
Объединить игроков MLBB и создать сильные команды!

Присоединяйтесь к сообществу! 🚀
        """
        bot.send_message(user_id, about_text, parse_mode='Markdown', reply_markup=create_fill_profile_keyboard())
        return
    bot.send_message(user_id, "✍️ Отлично, давайте создадим анкету и будем двигаться дальше.", reply_markup=types.ReplyKeyboardRemove())
    msg = bot.send_message(user_id, "Введите ваш игровой ник:")
    bot.register_next_step_handler(msg, process_nickname_step)

def process_nickname_step(message):
    """Шаг 1: Получение ника."""
    user_id = message.from_user.id
    if message.text == "⬅️ Назад": return back_to_start(message)
    user_data[user_id] = {'nickname': message.text}
    msg = bot.send_message(user_id, "Укажите ваш winrate в процентах (например, 58):")
    bot.register_next_step_handler(msg, process_winrate_step)

def process_winrate_step(message):
    """Шаг 2: Получение и проверка winrate."""
    user_id = message.from_user.id
    if message.text == "⬅️ Назад": return back_to_start(message)
    try:
        winrate = int(message.text)
        if not (0 <= winrate <= 100): raise ValueError()
        user_data[user_id]['winrate'] = winrate
        msg = bot.send_message(user_id, "На какой линии вы играете?", reply_markup=create_line_keyboard())
        bot.register_next_step_handler(msg, process_line_step)
    except (ValueError, TypeError):
        msg = bot.send_message(user_id, "Пожалуйста, введите ваш winrate цифрами (от 0 до 100).")
        bot.register_next_step_handler(msg, process_winrate_step)

def process_line_step(message):
    """Шаг 3: Получение линии."""
    user_id = message.from_user.id
    if message.text == "⬅️ Назад": return back_to_start(message)
    if message.text not in ["Gold Line", "Rome", "Средняя линия", "Лес", "XP Line", "Везде"]:
        msg = bot.send_message(user_id, "Пожалуйста, выберите линию с помощью кнопок.", reply_markup=create_line_keyboard())
        bot.register_next_step_handler(msg, process_line_step)
        return
    user_data[user_id]['line'] = message.text
    msg = bot.send_message(user_id, "Выберите ваш текущий ранг:", reply_markup=create_rank_keyboard())
    bot.register_next_step_handler(msg, process_rank_step)

def process_rank_step(message):
    """Шаг 4: Получение ранга."""
    user_id = message.from_user.id
    if message.text == "⬅️ Назад": return back_to_start(message)
    if message.text not in ["Воин", "Элита", "Мастер", "Грандмастер", "Эпик", "Легенда", "Мифический"]:
        msg = bot.send_message(user_id, "Пожалуйста, выберите ранг с помощью кнопок.", reply_markup=create_rank_keyboard())
        bot.register_next_step_handler(msg, process_rank_step)
        return
    user_data[user_id]['rank'] = message.text
    if message.text == "Мифический":
        msg = bot.send_message(user_id, "Выберите свой уровень мифического ранга:", reply_markup=create_mythic_rank_keyboard())
        bot.register_next_step_handler(msg, process_mythic_rank_step)
    else:
        user_data[user_id]['mythic_rank'] = None
        ask_goal_step(user_id)

def process_mythic_rank_step(message):
    """Шаг 4.1: Уточнение мифического ранга."""
    user_id = message.from_user.id
    if message.text == "⬅️ Назад": return back_to_start(message)
    if message.text not in ["Миф", "Мифическая честь", "Мифическая слава", "Мифический бессмертный"]:
        msg = bot.send_message(user_id, "Пожалуйста, выберите уровень с помощью кнопок.", reply_markup=create_mythic_rank_keyboard())
        bot.register_next_step_handler(msg, process_mythic_rank_step)
        return
    user_data[user_id]['mythic_rank'] = message.text
    ask_goal_step(user_id)

def ask_goal_step(user_id):
    """Шаг 5: Запрос цели игры."""
    msg = bot.send_message(user_id, "Какая ваша основная цель в игре? Это поможет найти людей со схожими целями.", reply_markup=create_goal_keyboard())
    bot.register_next_step_handler(msg, process_goal_step)

def process_goal_step(message):
    """Шаг 5: Обработка цели игры."""
    user_id = message.from_user.id
    if message.text == "⬅️ Назад": return back_to_start(message)
    if message.text not in ["Поднять ранг", "Поиграть для удовольствия", "Найти постоянную команду"]:
        msg = bot.send_message(user_id, "Пожалуйста, выберите цель с помощью кнопок.", reply_markup=create_goal_keyboard())
        bot.register_next_step_handler(msg, process_goal_step)
        return
    user_data[user_id]['goal'] = message.text
    msg = bot.send_message(user_id, "Расскажите немного о себе (например, ваш стиль игры, любимые герои). Это необязательно.", reply_markup=create_skip_keyboard())
    bot.register_next_step_handler(msg, process_about_step)

def process_about_step(message):
    """Шаг 6: Получение информации о себе."""
    user_id = message.from_user.id
    user_data[user_id]['about'] = None if message.text == "➡️ Далее" else message.text
    msg = bot.send_message(user_id, "И последний штрих! Хотите добавить фото, чтобы повысить доверие других игроков?", reply_markup=create_photo_keyboard())
    bot.register_next_step_handler(msg, process_photo_step)

def process_photo_step(message):
    """Шаг 7: Обработка фото или завершение."""
    user_id = message.from_user.id
    if message.text == "📷 Добавить фото":
        msg = bot.send_message(user_id, "Отправьте мне фото, которое будет в вашей анкете.", reply_markup=types.ReplyKeyboardRemove())
        bot.register_next_step_handler(msg, process_final_photo_upload)
    elif message.text == "➡️ Завершить":
        user_data[user_id]['photo_id'] = None
        finalize_profile(user_id, message.from_user.username)
    else:
        msg = bot.send_message(user_id, "Пожалуйста, используйте кнопки.", reply_markup=create_photo_keyboard())
        bot.register_next_step_handler(msg, process_photo_step)

@bot.message_handler(content_types=['photo'])
def process_final_photo_upload(message):
    """Обрабатывает загруженное фото и завершает регистрацию."""
    if message.from_user.id in user_data:
        user_id = message.from_user.id
        user_data[user_id]['photo_id'] = message.photo[-1].file_id
        finalize_profile(user_id, message.from_user.username)
    else:
        bot.send_message(message.from_user.id, "Вы можете добавить фото при редактировании анкеты.")

def finalize_profile(user_id, username):
    """Сохраняет анкету в БД, очищает временные данные и показывает главное меню."""
    user_data[user_id]['telegram_username'] = username
    save_profile(user_id, user_data[user_id])
    user_data.pop(user_id, None)
    bot.send_message(user_id, "🎉 Поздравляем! Ваша анкета создана. Добро пожаловать в главное меню!", reply_markup=create_main_menu_keyboard())

# --- ОБРАБОТЧИКИ ГЛАВНОГО МЕНЮ ---

@bot.message_handler(func=lambda message: message.text == "👤 Моя анкета")
def my_profile_handler(message):
    """Показывает анкету пользователя."""
    user_id = message.from_user.id
    update_last_active(user_id)
    profile = get_profile(user_id)
    if profile:
        caption = format_profile(profile)
        if profile.get('photo_id'):
            bot.send_photo(user_id, profile['photo_id'], caption=caption, reply_markup=create_my_profile_keyboard())
        else:
            bot.send_message(user_id, caption, reply_markup=create_my_profile_keyboard())
    else:
        bot.send_message(user_id, "Ваша анкета еще не создана.", reply_markup=create_fill_profile_keyboard())

@bot.message_handler(func=lambda message: message.text == "📊 Статистика")
def stats_handler(message):
    """Показывает статистику пользователя."""
    send_stats(message)

@bot.message_handler(func=lambda message: message.text == "🗑️ Удалить анкету")
def delete_profile_confirm(message):
    """Запрашивает подтверждение на удаление анкеты."""
    bot.send_message(message.from_user.id, "Вы уверены, что хотите удалить свою анкету? Это действие необратимо.", reply_markup=create_confirm_delete_keyboard())

@bot.message_handler(func=lambda message: message.text in ["Да, удалить", "Нет, отмена"])
def process_delete_confirmation(message):
    """Обрабатывает подтверждение удаления."""
    user_id = message.from_user.id
    if message.text == "Да, удалить":
        delete_profile(user_id)
        bot.send_message(user_id, "Ваша анкета была удалена.", reply_markup=types.ReplyKeyboardRemove())
        send_welcome(message)
    else:
        my_profile_handler(message)

@bot.message_handler(func=lambda message: message.text == "✏️ Редактировать анкету")
def edit_profile_handler(message):
    """Начинает процесс редактирования анкеты (через перезаполнение)."""
    bot.send_message(message.from_user.id, "Давайте обновим вашу анкету. Начнем сначала.")
    handle_start_options(message)

# --- ЛОГИКА ПОИСКА И ЛАЙКОВ ---
search_sessions = {}  # Хранит сессии поиска: {user_id: {'profiles': [], 'current_index': 0}}

@bot.message_handler(func=lambda message: message.text == "🚀 Быстрый поиск")
def quick_search_handler(message):
    """Начинает быстрый поиск активных игроков."""
    user_id = message.from_user.id
    update_last_active(user_id)
    profiles_found = get_active_profiles(user_id)
    if not profiles_found:
        bot.send_message(user_id, "😔 Активных игроков поблизости не найдено. Попробуйте позже.", reply_markup=create_main_menu_keyboard())
        return
    search_sessions[user_id] = {'profiles': profiles_found, 'current_index': 0}
    show_next_profile_in_search(user_id)

def show_next_profile_in_search(user_id, is_liked_by_flow=False):
    """Показывает следующую анкету из списка поиска."""
    session = search_sessions.get(user_id)
    if not session or session['current_index'] >= len(session['profiles']):
        bot.send_message(user_id, "✅ Поиск завершен. Больше анкет не найдено.", reply_markup=create_main_menu_keyboard())
        search_sessions.pop(user_id, None)
        return
    next_profile_id = session['profiles'][session['current_index']]
    profile_data = get_profile(next_profile_id)
    if not profile_data: # Пропускаем, если анкета была удалена
        session['current_index'] += 1
        show_next_profile_in_search(user_id, is_liked_by_flow)
        return
    caption = format_profile(profile_data)
    markup = create_liked_by_keyboard() if is_liked_by_flow else create_search_keyboard()
    if profile_data.get('photo_id'):
        bot.send_photo(user_id, profile_data['photo_id'], caption=caption, reply_markup=markup)
    else:
        bot.send_message(user_id, caption, reply_markup=markup)

@bot.message_handler(func=lambda message: message.text in ["👎 Следующий", "👎 Пропустить"])
def next_profile_handler(message):
    """Показывает следующую анкету в поиске."""
    user_id = message.from_user.id
    update_last_active(user_id)
    if user_id in search_sessions:
        search_sessions[user_id]['current_index'] += 1
        is_liked_by_flow = message.text == "👎 Пропустить"
        show_next_profile_in_search(user_id, is_liked_by_flow)

@bot.message_handler(func=lambda message: message.text in ["⏹️ Завершить поиск", "⏹️ Вернуться в меню", "⬅️ В меню"])
def stop_search_handler(message):
    """Завершает сессию поиска и возвращает в меню."""
    user_id = message.from_user.id
    search_sessions.pop(user_id, None)
    bot.send_message(user_id, "Возвращаю в главное меню.", reply_markup=create_main_menu_keyboard())

@bot.message_handler(func=lambda message: message.text in ["❤️ Нравится", "❤️ Нравится в ответ"])
def like_handler(message):
    """Обрабатывает лайк и проверяет на мэтч."""
    liker_id = message.from_user.id
    update_last_active(liker_id)
    if liker_id not in search_sessions: return
    session = search_sessions[liker_id]
    if session['current_index'] >= len(session['profiles']): return
    liked_id = session['profiles'][session['current_index']]
    
    # Добавляем лайк
    if add_like(liker_id, liked_id):
        bot.send_message(liker_id, "✅ Ваш лайк отправлен!")

    # Проверка на взаимный лайк (мэтч)
    if check_mutual_like(liker_id, liked_id):
        liker_profile = get_profile(liker_id)
        liked_profile = get_profile(liked_id)
        if liker_profile and liked_profile:
            liker_username = f"@{liker_profile['telegram_username']}" if liker_profile.get('telegram_username') else "профиль"
            liked_username = f"@{liked_profile['telegram_username']}" if liked_profile.get('telegram_username') else "профиль"
            bot.send_message(liker_id, f"🎉 Мэтч! Вы понравились игроку {liked_profile['nickname']}. Начните общение: {liked_username}")
            bot.send_message(liked_id, f"🎉 Мэтч! Вы понравились игроку {liker_profile['nickname']}. Начните общение: {liker_username}")

    is_liked_by_flow = message.text == "❤️ Нравится в ответ"
    search_sessions[liker_id]['current_index'] += 1
    show_next_profile_in_search(liker_id, is_liked_by_flow)

@bot.message_handler(func=lambda message: message.text == "❤️ Понравился")
def liked_by_list_handler(message):
    """Показывает список тех, кто лайкнул пользователя."""
    user_id = message.from_user.id
    update_last_active(user_id)
    profiles_found = get_likes_for_user(user_id)
    if not profiles_found:
        bot.send_message(user_id, "😔 Пока что ваша анкета никому не понравилась. Не переживайте, вас скоро заметят!", reply_markup=create_main_menu_keyboard())
        return
    bot.send_message(user_id, "💌 Эти игроки проявили к вам интерес. Посмотрим?")
    search_sessions[user_id] = {'profiles': profiles_found, 'current_index': 0}
    show_next_profile_in_search(user_id, is_liked_by_flow=True)

@bot.message_handler(func=lambda message: message.text == "⚙️ Поиск тиммейта")
def detailed_search_handler(message):
    """Заглушка для детального поиска."""
    update_last_active(message.from_user.id)
    bot.send_message(message.from_user.id, "🛠 Функция детального поиска с фильтрами находится в разработке и скоро будет добавлена!", reply_markup=create_main_menu_keyboard())

@bot.message_handler(func=lambda message: True)
def handle_all_text(message):
    """Обрабатывает любой текст, который не подошел под другие обработчики."""
    user_id = message.from_user.id
    if user_exists(user_id):
        update_last_active(user_id)
        bot.send_message(user_id, "Используйте кнопки в меню для навигации.", reply_markup=create_main_menu_keyboard())
    else:
        send_welcome(message)

# --- ЗАПУСК БОТА ---
if __name__ == '__main__':
    print("🤖 Инициализация Telegram бота для поиска тиммейтов MLBB")
    print("=" * 60)
    print("📦 Инициализация базы данных...")
    init_db()
    print("✅ База данных готова.")
    print("🚀 Бот запускается...")
    print("📱 Найдите своего бота в Telegram и отправьте /start")
    print("=" * 60)
    try:
        bot.polling(none_stop=True, timeout=60)
    except KeyboardInterrupt:
        print("\n🛑 Бот остановлен пользователем")
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        print("🔄 Перезапуск через 5 секунд...")
        import time
        time.sleep(5)
        bot.polling(none_stop=True, timeout=60)
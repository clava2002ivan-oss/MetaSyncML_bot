# -*- coding: utf-8 -*-

# --- БИБЛИОТЕКИ ---
import telebot
from telebot import types
import os
from datetime import datetime
from config import get_token
from database import Database

# --- НАСТРОЙКИ И БЕЗОПАСНОСТЬ ---
TOKEN = get_token()

# --- ИНИЦИАЛИЗАЦИЯ БОТА И ДАННЫХ ---
bot = telebot.TeleBot(TOKEN)
# Словарь для временного хранения данных при регистрации анкеты
user_data = {}
# Глобальный экземпляр базы данных
db = Database()

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
    markup.row("Золотая линия", "Роам", "Средняя линия")
    markup.row("Лес", "XP линия", "Везде")
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

# --- ОСНОВНЫЕ ОБРАБОТЧИКИ КОМАНД И СООБЩЕНИЙ ---

@bot.message_handler(commands=['start'])
def send_welcome(message):
    """Обработчик команды /start."""
    user_id = message.from_user.id
    if db.user_exists(user_id):
        db.update_last_active(user_id)
        bot.send_message(user_id, "С возвращением! Добро пожаловать в главное меню.", reply_markup=create_main_menu_keyboard())
    else:
        bot.send_message(message.chat.id, "👋 Привет! Хочешь найти тиммейтов для Mobile Legends?", reply_markup=create_start_keyboard())

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
        bot.send_message(user_id, "Этот раздел в разработке. Здесь будет информация о проекте.", reply_markup=create_fill_profile_keyboard())
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
    if message.text not in ["Золотая линия", "Роам", "Средняя линия", "Лес", "XP линия", "Везде"]:
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
    db.save_profile(user_id, user_data[user_id])
    user_data.pop(user_id, None)
    bot.send_message(user_id, "🎉 Поздравляем! Ваша анкета создана. Добро пожаловать в главное меню!", reply_markup=create_main_menu_keyboard())

# --- ОБРАБОТЧИКИ ГЛАВНОГО МЕНЮ ---

def my_profile_handler(message):
    """Показывает анкету пользователя."""
    user_id = message.from_user.id
    db.update_last_active(user_id)
    profile = db.get_profile(user_id)
    if profile:
        caption = format_profile(profile)
        if profile.get('photo_id'):
            bot.send_photo(user_id, profile['photo_id'], caption=caption, reply_markup=create_my_profile_keyboard())
        else:
            bot.send_message(user_id, caption, reply_markup=create_my_profile_keyboard())
    else:
        bot.send_message(user_id, "Ваша анкета еще не создана.", reply_markup=create_fill_profile_keyboard())

@bot.message_handler(func=lambda message: message.text == "🗑️ Удалить анкету")
def delete_profile_confirm(message):
    """Запрашивает подтверждение на удаление анкеты."""
    bot.send_message(message.from_user.id, "Вы уверены, что хотите удалить свою анкету? Это действие необратимо.", reply_markup=create_confirm_delete_keyboard())

@bot.message_handler(func=lambda message: message.text in ["Да, удалить", "Нет, отмена"])
def process_delete_confirmation(message):
    """Обрабатывает подтверждение удаления."""
    user_id = message.from_user.id
    if message.text == "Да, удалить":
        db.delete_profile(user_id)
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

def quick_search_handler(message):
    """Начинает быстрый поиск активных игроков."""
    user_id = message.from_user.id
    db.update_last_active(user_id)
    profiles_found = db.get_active_profiles(user_id)
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
    profile_data = db.get_profile(next_profile_id)
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
    db.update_last_active(user_id)
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
    db.update_last_active(liker_id)
    if liker_id not in search_sessions: return
    session = search_sessions[liker_id]
    if session['current_index'] >= len(session['profiles']): return
    liked_id = session['profiles'][session['current_index']]
    
    # Добавляем лайк
    if db.add_like(liker_id, liked_id):
        bot.send_message(liker_id, "✅ Ваш лайк отправлен!")

    # Проверка на взаимный лайк (мэтч)
    if db.check_mutual_like(liker_id, liked_id):
        liker_profile = db.get_profile(liker_id)
        liked_profile = db.get_profile(liked_id)
        if liker_profile and liked_profile:
            liker_username = f"@{liker_profile['telegram_username']}" if liker_profile.get('telegram_username') else "профиль"
            liked_username = f"@{liked_profile['telegram_username']}" if liked_profile.get('telegram_username') else "профиль"
            bot.send_message(liker_id, f"🎉 Мэтч! Вы понравились игроку {liked_profile['nickname']}. Начните общение: {liked_username}")
            bot.send_message(liked_id, f"🎉 Мэтч! Вы понравились игроку {liker_profile['nickname']}. Начните общение: {liker_username}")

    is_liked_by_flow = message.text == "❤️ Нравится в ответ"
    search_sessions[liker_id]['current_index'] += 1
    show_next_profile_in_search(liker_id, is_liked_by_flow)

def liked_by_list_handler(message):
    """Показывает список тех, кто лайкнул пользователя."""
    user_id = message.from_user.id
    db.update_last_active(user_id)
    profiles_found = db.get_likes_for_user(user_id)
    if not profiles_found:
        bot.send_message(user_id, "😔 Пока что ваша анкета никому не понравилась. Не переживайте, вас скоро заметят!", reply_markup=create_main_menu_keyboard())
        return
    bot.send_message(user_id, "💌 Эти игроки проявили к вам интерес. Посмотрим?")
    search_sessions[user_id] = {'profiles': profiles_found, 'current_index': 0}
    show_next_profile_in_search(user_id, is_liked_by_flow=True)

@bot.message_handler(func=lambda message: message.text == "⚙️ Поиск тиммейта")
def detailed_search_handler(message):
    """Заглушка для детального поиска."""
    db.update_last_active(message.from_user.id)
    bot.send_message(message.from_user.id, "🛠 Функция детального поиска с фильтрами находится в разработке и скоро будет добавлена!", reply_markup=create_main_menu_keyboard())

@bot.message_handler(func=lambda message: message.text in ["🚀 Быстрый поиск", "👤 Моя анкета", "❤️ Понравился"])
def main_menu_buttons_handler(message):
    """Обработчик для кнопок главного меню, чтобы бот реагировал сразу после перезапуска."""
    user_id = message.from_user.id
    if not db.user_exists(user_id):
        send_welcome(message)
        return
    
    db.update_last_active(user_id)
    
    if message.text == "🚀 Быстрый поиск":
        quick_search_handler(message)
    elif message.text == "👤 Моя анкета":
        my_profile_handler(message)
    elif message.text == "❤️ Понравился":
        liked_by_list_handler(message)

@bot.message_handler(func=lambda message: True)
def handle_all_text(message):
    """Обрабатывает любой текст, который не подошел под другие обработчики."""
    user_id = message.from_user.id
    if db.user_exists(user_id):
        db.update_last_active(user_id)
        bot.send_message(user_id, "Используйте кнопки в меню для навигации.", reply_markup=create_main_menu_keyboard())
    else:
        send_welcome(message)

# --- ЗАПУСК БОТА ---
if __name__ == '__main__':
    print("🤖 Инициализация Telegram бота для поиска тиммейтов MLBB")
    print("=" * 60)
    print("📦 База данных инициализирована.")
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
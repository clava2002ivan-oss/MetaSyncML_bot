import os
from dotenv import load_dotenv

# Загружаем переменные окружения из файла .env
load_dotenv()

def get_token():
    """Получает токен бота из переменных окружения или файла .env"""
    token = os.getenv('TOKEN')
    if not token:
        print("❌ ОШИБКА: Токен бота не найден!")
        print("")
        print("Установите токен одним из способов:")
        print("1. Переменная окружения: export TOKEN='ваш_токен'")
        print("2. Файл .env: создайте файл .env с содержимым TOKEN=ваш_токен")
        print("")
        print("Как получить токен:")
        print("1. Найдите @BotFather в Telegram")
        print("2. Отправьте /newbot")
        print("3. Следуйте инструкциям")
        exit(1)
    return token

# Настройки базы данных
DATABASE_NAME = 'mlbb_finder.db'

# Настройки поиска
ACTIVE_TIMEOUT_MINUTES = 10  # Время активности пользователя в минутах

# Настройки интерфейса
MAX_PROFILES_PER_SEARCH = 50  # Максимальное количество профилей в поиске
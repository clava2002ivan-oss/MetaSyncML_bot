# 🚀 Развертывание Telegram бота на PythonAnywhere

## Шаг 1: Подготовка аккаунта PythonAnywhere

### 1.1 Создание аккаунта
1. Перейдите на [www.pythonanywhere.com](https://www.pythonanywhere.com)
2. Зарегистрируйтесь (бесплатный аккаунт подходит для бота)
3. Войдите в свой аккаунт

### 1.2 Настройка рабочего пространства
1. Откройте **Consoles** → **Bash**
2. Создайте папку для проекта:
```bash
mkdir ~/telegram_bot
cd ~/telegram_bot
```

## Шаг 2: Загрузка файлов проекта

### 2.1 Загрузка через Git (рекомендуется)
```bash
# Клонируйте репозиторий (если есть)
git clone https://github.com/your-username/telegram-bot.git .

# Или создайте файлы вручную
```

### 2.2 Загрузка файлов вручную
1. Откройте **Files** в PythonAnywhere
2. Перейдите в папку `telegram_bot`
3. Загрузите все файлы проекта:
   - `main_improved.py`
   - `config.py`
   - `requirements.txt`
   - `.env` (создайте с вашим токеном)

## Шаг 3: Настройка окружения

### 3.1 Установка зависимостей
В консоли Bash выполните:
```bash
cd ~/telegram_bot
pip3 install --user -r requirements.txt
```

### 3.2 Создание файла .env
```bash
# Создайте файл .env
echo "TOKEN=ваш_токен_от_botfather" > .env
```

### 3.3 Проверка установки
```bash
python3 test_bot.py
```

## Шаг 4: Настройка Web App (для Always-on бота)

### 4.1 Создание Web App
1. Откройте **Web** в PythonAnywhere
2. Нажмите **Add a new web app**
3. Выберите **Manual configuration**
4. Выберите **Python 3.9** (или новее)

### 4.2 Настройка WSGI файла
1. Откройте файл `/var/www/yourusername_pythonanywhere_com_wsgi.py`
2. Замените содержимое на:

```python
import sys
import os

# Добавляем путь к проекту
path = '/home/yourusername/telegram_bot'
if path not in sys.path:
    sys.path.append(path)

# Устанавливаем переменную окружения
os.environ['TOKEN'] = 'ваш_токен_от_botfather'

# Импортируем и запускаем бота
from main_improved import bot

# Создаем WSGI приложение
def application(environ, start_response):
    # Простой ответ для проверки работы
    status = '200 OK'
    output = b'Telegram Bot is running!'
    
    response_headers = [('Content-type', 'text/plain'),
                       ('Content-Length', str(len(output)))]
    start_response(status, response_headers)
    
    return [output]
```

### 4.3 Настройка виртуального окружения
1. В настройках Web App найдите **Virtual environment**
2. Укажите путь: `/home/yourusername/.local`

## Шаг 5: Настройка Always-on бота

### 5.1 Создание скрипта запуска
Создайте файл `run_bot_always.py`:

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Скрипт для запуска бота в режиме Always-on на PythonAnywhere
"""

import os
import sys
import time
import logging
from datetime import datetime

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/home/yourusername/telegram_bot/bot.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

def main():
    """Основная функция запуска бота."""
    try:
        # Проверяем наличие токена
        token = os.getenv('TOKEN')
        if not token:
            logger.error("Токен бота не найден! Установите переменную TOKEN")
            return
        
        logger.info("Запуск Telegram бота...")
        
        # Импортируем бота
        from main_improved import bot, init_db
        
        # Инициализируем базу данных
        init_db()
        logger.info("База данных инициализирована")
        
        # Запускаем бота
        logger.info("Бот запущен и готов к работе!")
        bot.polling(none_stop=True, timeout=60)
        
    except KeyboardInterrupt:
        logger.info("Бот остановлен пользователем")
    except Exception as e:
        logger.error(f"Ошибка запуска бота: {e}")
        time.sleep(5)
        main()  # Перезапуск

if __name__ == '__main__':
    main()
```

### 5.2 Настройка Always-on задачи
1. Откройте **Tasks** в PythonAnywhere
2. Добавьте новую задачу:
   - **Command**: `cd ~/telegram_bot && python3 run_bot_always.py`
   - **Schedule**: Daily
   - **Time**: Now (или удобное время)

## Шаг 6: Альтернативный способ - Webhook

### 6.1 Создание Webhook бота
Создайте файл `webhook_bot.py`:

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Версия бота с Webhook для PythonAnywhere
"""

import os
import telebot
from flask import Flask, request
from config import get_token, DATABASE_NAME, ACTIVE_TIMEOUT_MINUTES, MAX_PROFILES_PER_SEARCH

# Инициализация Flask
app = Flask(__name__)

# Инициализация бота
bot = telebot.TeleBot(get_token())

# Webhook URL
WEBHOOK_URL = 'https://yourusername.pythonanywhere.com/webhook'

@app.route('/webhook', methods=['POST'])
def webhook():
    """Обработчик webhook от Telegram."""
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return 'OK'
    else:
        return 'Error'

@app.route('/')
def index():
    """Главная страница для проверки работы."""
    return 'Telegram Bot is running!'

@app.route('/set_webhook')
def set_webhook():
    """Установка webhook."""
    bot.remove_webhook()
    bot.set_webhook(url=WEBHOOK_URL)
    return 'Webhook set!'

@app.route('/remove_webhook')
def remove_webhook():
    """Удаление webhook."""
    bot.remove_webhook()
    return 'Webhook removed!'

# Импортируем все обработчики из основного файла
from main_improved import *

if __name__ == '__main__':
    # Инициализируем базу данных
    init_db()
    
    # Устанавливаем webhook
    bot.remove_webhook()
    bot.set_webhook(url=WEBHOOK_URL)
    
    print("Webhook установлен!")
    print("Бот готов к работе!")
    
    # Запускаем Flask приложение
    app.run(host='0.0.0.0', port=5000)
```

### 6.2 Настройка WSGI для Webhook
Обновите WSGI файл:

```python
import sys
import os

# Добавляем путь к проекту
path = '/home/yourusername/telegram_bot'
if path not in sys.path:
    sys.path.append(path)

# Устанавливаем переменную окружения
os.environ['TOKEN'] = 'ваш_токен_от_botfather'

# Импортируем Flask приложение
from webhook_bot import app as application
```

## Шаг 7: Проверка и тестирование

### 7.1 Проверка файлов
```bash
cd ~/telegram_bot
ls -la
```

### 7.2 Тестирование бота
```bash
python3 test_bot.py
```

### 7.3 Проверка Web App
1. Откройте ваш сайт: `https://yourusername.pythonanywhere.com`
2. Должно появиться сообщение "Telegram Bot is running!"

### 7.4 Проверка Webhook (если используется)
1. Перейдите на: `https://yourusername.pythonanywhere.com/set_webhook`
2. Должно появиться "Webhook set!"

## Шаг 8: Мониторинг и логи

### 8.1 Просмотр логов
```bash
# Логи бота
tail -f ~/telegram_bot/bot.log

# Логи PythonAnywhere
tail -f ~/.local/share/pythonanywhere/logfiles/yourusername.pythonanywhere.com.error.log
```

### 8.2 Проверка статуса
```bash
# Проверка процессов
ps aux | grep python

# Проверка использования памяти
free -h
```

## Шаг 9: Обновление бота

### 9.1 Обновление кода
```bash
cd ~/telegram_bot
# Загрузите новые файлы через Files или Git
```

### 9.2 Перезапуск
```bash
# Для Always-on задачи
# Просто обновите файлы, задача перезапустится автоматически

# Для Web App
# Нажмите "Reload" в настройках Web App
```

## Полезные команды

```bash
# Проверка статуса бота
curl https://yourusername.pythonanywhere.com

# Просмотр логов в реальном времени
tail -f ~/telegram_bot/bot.log

# Проверка переменных окружения
echo $TOKEN

# Перезапуск Web App
touch /var/www/yourusername_pythonanywhere_com_wsgi.py
```

## Устранение неполадок

### Бот не отвечает
1. Проверьте логи: `tail -f ~/telegram_bot/bot.log`
2. Убедитесь, что токен правильный
3. Проверьте статус Web App

### Ошибки импорта
1. Убедитесь, что все зависимости установлены
2. Проверьте пути в WSGI файле
3. Перезапустите Web App

### Проблемы с базой данных
1. Проверьте права доступа к файлу БД
2. Убедитесь, что папка существует
3. Проверьте логи на ошибки SQL

## Готово! 🎉

Ваш Telegram бот теперь работает на PythonAnywhere и будет доступен 24/7!
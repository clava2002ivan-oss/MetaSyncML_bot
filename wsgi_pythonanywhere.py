# -*- coding: utf-8 -*-
"""
WSGI файл для развертывания Telegram бота на PythonAnywhere
Замените 'yourusername' на ваше имя пользователя PythonAnywhere
"""

import sys
import os

# Добавляем путь к проекту
path = '/home/yourusername/telegram_bot'
if path not in sys.path:
    sys.path.append(path)

# Устанавливаем переменную окружения для токена
# Замените 'your_token_here' на ваш токен от @BotFather
os.environ['TOKEN'] = 'your_token_here'

# Импортируем Flask приложение из webhook_bot
from webhook_bot import app as application

# Альтернативный вариант - простой ответ без webhook
# def application(environ, start_response):
#     status = '200 OK'
#     output = b'Telegram Bot is running!'
#     
#     response_headers = [('Content-type', 'text/plain'),
#                        ('Content-Length', str(len(output)))]
#     start_response(status, response_headers)
#     
#     return [output]
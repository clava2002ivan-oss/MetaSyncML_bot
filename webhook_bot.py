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

# Webhook URL (замените yourusername на ваше имя пользователя)
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

@app.route('/status')
def status():
    """Страница статуса бота."""
    try:
        webhook_info = bot.get_webhook_info()
        return f"""
        <h1>Статус Telegram бота</h1>
        <p>Webhook URL: {webhook_info.url}</p>
        <p>Статус: {'Активен' if webhook_info.url else 'Неактивен'}</p>
        <p>Ошибки: {webhook_info.last_error_message or 'Нет'}</p>
        <p><a href="/set_webhook">Установить webhook</a></p>
        <p><a href="/remove_webhook">Удалить webhook</a></p>
        """
    except Exception as e:
        return f"Ошибка получения статуса: {e}"

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
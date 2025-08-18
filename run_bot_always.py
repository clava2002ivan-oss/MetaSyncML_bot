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
        token = os.getenv('TELEGRAM_TOKEN') or os.getenv('TOKEN')
        if not token:
            logger.error("Токен бота не найден! Установите переменную TELEGRAM_TOKEN (или TOKEN)")
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
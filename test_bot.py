#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Тестовый скрипт для проверки основных функций Telegram бота
"""

import sqlite3
import os
from datetime import datetime, timedelta

def test_database_connection():
    """Тестирует подключение к базе данных."""
    print("🔍 Тестирование подключения к базе данных...")
    try:
        conn = sqlite3.connect('mlbb_finder.db')
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        print(f"✅ База данных подключена. Найдено таблиц: {len(tables)}")
        for table in tables:
            print(f"   - {table[0]}")
        conn.close()
        return True
    except Exception as e:
        print(f"❌ Ошибка подключения к базе данных: {e}")
        return False

def test_environment():
    """Тестирует переменные окружения."""
    print("\n🔍 Тестирование переменных окружения...")
    token = os.getenv('TOKEN')
    if token:
        print("✅ Токен бота найден")
        print(f"   Длина токена: {len(token)} символов")
        return True
    else:
        print("❌ Токен бота не найден")
        print("   Установите токен: export TOKEN='ваш_токен'")
        return False

def test_dependencies():
    """Тестирует установленные зависимости."""
    print("\n🔍 Тестирование зависимостей...")
    try:
        import telebot
        print("✅ pyTelegramBotAPI установлен")
    except ImportError:
        print("❌ pyTelegramBotAPI не установлен")
        return False
    
    try:
        from dotenv import load_dotenv
        print("✅ python-dotenv установлен")
    except ImportError:
        print("❌ python-dotenv не установлен")
        return False
    
    return True

def test_config_file():
    """Тестирует конфигурационный файл."""
    print("\n🔍 Тестирование конфигурационного файла...")
    try:
        from config import get_token, DATABASE_NAME, ACTIVE_TIMEOUT_MINUTES
        print("✅ Конфигурационный файл загружен")
        print(f"   База данных: {DATABASE_NAME}")
        print(f"   Таймаут активности: {ACTIVE_TIMEOUT_MINUTES} минут")
        return True
    except ImportError as e:
        print(f"❌ Ошибка загрузки конфигурации: {e}")
        return False

def test_sample_data():
    """Тестирует создание тестовых данных."""
    print("\n🔍 Тестирование создания тестовых данных...")
    try:
        conn = sqlite3.connect('mlbb_finder.db')
        cursor = conn.cursor()
        
        # Создаем тестовый профиль
        test_user_id = 123456789
        test_data = {
            'telegram_username': 'test_user',
            'nickname': 'TestPlayer',
            'winrate': 65,
            'line': 'Средняя линия',
            'rank': 'Эпик',
            'mythic_rank': None,
            'goal': 'Поднять ранг',
            'about': 'Тестовый игрок',
            'photo_id': None
        }
        
        cursor.execute('''
        INSERT OR REPLACE INTO profiles 
        (user_id, telegram_username, nickname, winrate, line, rank, mythic_rank, goal, about, photo_id, last_active) 
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (test_user_id, test_data['telegram_username'], test_data['nickname'], 
              test_data['winrate'], test_data['line'], test_data['rank'], 
              test_data['mythic_rank'], test_data['goal'], test_data['about'], 
              test_data['photo_id'], datetime.now()))
        
        conn.commit()
        
        # Проверяем, что данные сохранились
        cursor.execute("SELECT nickname FROM profiles WHERE user_id = ?", (test_user_id,))
        result = cursor.fetchone()
        if result and result[0] == 'TestPlayer':
            print("✅ Тестовые данные созданы успешно")
            
            # Удаляем тестовые данные
            cursor.execute("DELETE FROM profiles WHERE user_id = ?", (test_user_id,))
            conn.commit()
            print("✅ Тестовые данные удалены")
        else:
            print("❌ Ошибка создания тестовых данных")
        
        conn.close()
        return True
    except Exception as e:
        print(f"❌ Ошибка работы с тестовыми данными: {e}")
        return False

def main():
    """Основная функция тестирования."""
    print("🧪 Тестирование Telegram бота для поиска тиммейтов MLBB")
    print("=" * 60)
    
    tests = [
        test_dependencies,
        test_environment,
        test_config_file,
        test_database_connection,
        test_sample_data
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
    
    print("\n" + "=" * 60)
    print(f"📊 Результаты тестирования: {passed}/{total} тестов пройдено")
    
    if passed == total:
        print("🎉 Все тесты пройдены! Бот готов к запуску.")
        print("\n🚀 Для запуска бота выполните:")
        print("   ./run_bot.sh")
        print("   или")
        print("   python main_improved.py")
    else:
        print("⚠️  Некоторые тесты не пройдены. Проверьте настройки.")
        print("\n🔧 Рекомендации:")
        print("   1. Установите зависимости: pip install -r requirements.txt")
        print("   2. Установите токен бота: export TOKEN='ваш_токен'")
        print("   3. Проверьте права доступа к файлам")

if __name__ == '__main__':
    main()
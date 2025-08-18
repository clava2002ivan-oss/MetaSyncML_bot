#!/bin/bash

# Скрипт для запуска Telegram бота

echo "🤖 Запуск Telegram бота для поиска тиммейтов MLBB"
echo "================================================"

# Проверяем, активировано ли виртуальное окружение
if [[ "$VIRTUAL_ENV" == "" ]]; then
    echo "📦 Активируем виртуальное окружение..."
    source venv/bin/activate
fi

# Проверяем наличие токена
if [[ -z "$TOKEN" ]]; then
    echo "❌ ОШИБКА: Токен бота не найден!"
    echo ""
    echo "Для установки токена выполните:"
    echo "export TOKEN='ваш_токен_от_botfather'"
    echo ""
    echo "Или добавьте токен в файл .env:"
    echo "echo 'TOKEN=ваш_токен' > .env"
    echo ""
    echo "Как получить токен:"
    echo "1. Найдите @BotFather в Telegram"
    echo "2. Отправьте /newbot"
    echo "3. Следуйте инструкциям"
    exit 1
fi

echo "✅ Токен найден"
echo "🚀 Запускаем бота..."

# Запускаем бота
python main.py
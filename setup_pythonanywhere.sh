#!/bin/bash

# Скрипт для автоматической настройки Telegram бота на PythonAnywhere
# Запустите этот скрипт в консоли PythonAnywhere

echo "🚀 Настройка Telegram бота на PythonAnywhere"
echo "============================================="

# Проверяем, что мы в PythonAnywhere
if [[ ! "$HOSTNAME" == *"pythonanywhere"* ]]; then
    echo "❌ Этот скрипт предназначен для запуска на PythonAnywhere"
    exit 1
fi

# Получаем имя пользователя
USERNAME=$(whoami)
echo "👤 Пользователь: $USERNAME"

# Создаем папку для проекта
echo "📁 Создание папки проекта..."
mkdir -p ~/telegram_bot
cd ~/telegram_bot

# Проверяем наличие файлов
if [ ! -f "main_improved.py" ]; then
    echo "❌ Файл main_improved.py не найден!"
    echo "   Загрузите файлы проекта в папку ~/telegram_bot"
    exit 1
fi

# Устанавливаем зависимости
echo "📦 Установка зависимостей..."
pip3 install --user -r requirements.txt

# Проверяем токен
if [ -z "$TOKEN" ]; then
    echo "⚠️  Токен бота не установлен"
    echo "   Установите токен: export TOKEN='ваш_токен'"
    echo "   Или создайте файл .env с токеном"
fi

# Создаем файл .env если его нет
if [ ! -f ".env" ]; then
    echo "📝 Создание файла .env..."
    if [ ! -z "$TOKEN" ]; then
        echo "TOKEN=$TOKEN" > .env
        echo "✅ Файл .env создан с токеном из переменной окружения"
    else
        echo "TOKEN=your_token_here" > .env
        echo "⚠️  Файл .env создан. Замените 'your_token_here' на ваш токен"
    fi
fi

# Обновляем пути в файлах
echo "🔧 Обновление путей в файлах..."
sed -i "s/yourusername/$USERNAME/g" run_bot_always.py
sed -i "s/yourusername/$USERNAME/g" webhook_bot.py

# Создаем лог файл
touch bot.log
chmod 644 bot.log

# Тестируем установку
echo "🧪 Тестирование установки..."
python3 test_bot.py

echo ""
echo "✅ Настройка завершена!"
echo ""
echo "📋 Следующие шаги:"
echo "1. Откройте Web в PythonAnywhere"
echo "2. Создайте новый Web App"
echo "3. Выберите Manual configuration"
echo "4. Скопируйте содержимое wsgi_pythonanywhere.py в WSGI файл"
echo "5. Замените 'yourusername' на '$USERNAME' в WSGI файле"
echo "6. Замените 'your_token_here' на ваш токен"
echo "7. Нажмите Reload"
echo ""
echo "🌐 Ваш сайт будет доступен по адресу:"
echo "   https://$USERNAME.pythonanywhere.com"
echo ""
echo "📱 Для проверки бота перейдите на:"
echo "   https://$USERNAME.pythonanywhere.com/status"
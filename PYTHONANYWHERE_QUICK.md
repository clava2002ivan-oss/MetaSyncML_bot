# ⚡ Быстрое развертывание на PythonAnywhere

## Шаг 1: Подготовка
1. Зарегистрируйтесь на [pythonanywhere.com](https://www.pythonanywhere.com)
2. Получите токен бота у @BotFather в Telegram

## Шаг 2: Загрузка файлов
1. Откройте **Files** в PythonAnywhere
2. Создайте папку `telegram_bot`
3. Загрузите файлы:
   - `main_improved.py`
   - `config.py`
   - `requirements.txt`
   - `webhook_bot.py`
   - `wsgi_pythonanywhere.py`
   - `setup_pythonanywhere.sh`

## Шаг 3: Автоматическая настройка
1. Откройте **Consoles** → **Bash**
2. Выполните:
```bash
cd ~/telegram_bot
chmod +x setup_pythonanywhere.sh
./setup_pythonanywhere.sh
```

## Шаг 4: Настройка Web App
1. Откройте **Web** → **Add a new web app**
2. Выберите **Manual configuration** → **Python 3.9**
3. Откройте WSGI файл и замените содержимое на код из `wsgi_pythonanywhere.py`
4. Замените `yourusername` на ваше имя пользователя
5. Замените `your_token_here` на ваш токен
6. Нажмите **Reload**

## Шаг 5: Проверка
1. Откройте ваш сайт: `https://yourusername.pythonanywhere.com`
2. Проверьте статус: `https://yourusername.pythonanywhere.com/status`
3. Установите webhook: `https://yourusername.pythonanywhere.com/set_webhook`

## Готово! 🎉

Ваш бот теперь работает 24/7 на PythonAnywhere!

---

**Проблемы?** Проверьте логи в консоли PythonAnywhere.
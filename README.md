# MLBB Team Finder — бот «Sil»

Sil — Telegram-бот для поиска тиммейтов в Mobile Legends: Bang Bang. Бот ведёт диалог на русском языке, сохраняет анкеты игроков и помогает находить напарников по рангу, роли и целям.

## Технологии
- Python 3.12
- python-telegram-bot 20.x (async, `Application.run_polling()`)
- SQLite3 (локально, через `database.py`)
- PicklePersistence (`bot_data.pkl`) — кнопки продолжают работать после рестартов
- Деплой: PythonAnywhere (Always-on task)

## Быстрый старт (локально)
1. Установите зависимости:
```bash
pip install -r requirements.txt
```
2. Создайте файл `.env` по образцу:
```bash
cp .env.example .env
# Заполните TELEGRAM_TOKEN=...
```
3. Запустите бота:
```bash
python3 main.py
```

## Деплой на PythonAnywhere
- Загрузите файлы `main.py` и `database.py` в корень проекта.
- Установите зависимости из `requirements.txt` (через Bash-консоль PA).
- Создайте Always-on task со строкой запуска:
```bash
cd /home/USERNAME/YOUR_APP_DIR && source .venv/bin/activate && python3 main.py
```
- Для обновления достаточно перезалить новые версии `main.py` и/или `database.py` и перезапустить Always-on task в веб-интерфейсе.

## Конфигурация
- Переменная окружения `TELEGRAM_TOKEN` из `.env`. Загрузка осуществляется через `python-dotenv` в `main.py`.
- Файл БД: `mlbb.db` в рабочем каталоге (можно переопределить `MLBB_DB_PATH`).

## Примечания
- Формат профиля совместим с кодом в `main.py` (`UserProfile`, лайки, просмотры, статистика).
- При первом запуске таблицы создаются автоматически.
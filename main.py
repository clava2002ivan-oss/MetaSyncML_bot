# main.py
# MLBB Team Finder bot ("Sil") — Telegram bot using python-telegram-bot v20
import os
import time
import logging
import random
from enum import Enum, auto
from typing import Optional, List, Dict, Any

from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, Bot
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters,
    PicklePersistence,
)
from telegram.error import TelegramError

from dotenv import load_dotenv
load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
if not TELEGRAM_TOKEN:
    raise RuntimeError("ОШИБКА: TELEGRAM_TOKEN не найден. Укажи его в переменных окружения или .env")

import database as db  # our data layer

# -------- Logging --------
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    handlers=[
        logging.FileHandler("bot.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# -------- Constants (Russian UI) --------
RANKS = ["Воин", "Элита", "Мастер", "Грандмастер", "Эпик", "Легенда", "Мифический"]
MYTHIC_RANKS = ["Миф", "Мифическая честь", "Мифическая слава", "Мифический бессмертный"]
ALL_RANKS = RANKS[:-1] + ["Мифический (любой)"] + MYTHIC_RANKS

# Линии полностью на русском (как просил пользователь)
LINES = ["Голд", "Роум", "Мид", "Лес", "Эксп", "Везде"]
GOALS = ["Поднять ранг", "Поиграть для удовольствия", "Найти постоянную команду"]
WINRATE_FILTERS = ["+/- 5%", "+/- 10%", "Неважно"]
ACTIVE_WINDOWS = ["3 минуты", "5 минут", "10 минут"]  # Добавлены варианты времени активности

# Быстрый поиск: активность не старше 3 минут (по умолчанию)
DEFAULT_QUICK_SEARCH_ACTIVE_WINDOW = 3 * 60  # seconds

# Максимальное количество фотографий в профиле
MAX_PHOTOS = 5

# Максимальная длина текста "О себе" для отображения в карточке
MAX_ABOUT_LENGTH = 200

# -------- States --------
class States(Enum):
    SELECTING_ACTION = auto()
    GET_NICKNAME = auto()
    GET_WINRATE = auto()
    GET_LINE = auto()
    GET_RANK = auto()
    GET_MYTHIC_RANK = auto()
    GET_GOAL = auto()
    GET_ABOUT = auto()
    GET_PHOTO = auto()
    MAIN_MENU = auto()
    MY_PROFILE = auto()
    DELETE_CONFIRM = auto()
    EDIT_PROFILE_CHOICE = auto()
    EDIT_PROFILE_INPUT = auto()
    EDIT_MYTHIC_RANK = auto()
    QUICK_SEARCH_SETUP = auto()
    QUICK_SEARCH_VIEWING = auto()
    ADVANCED_SEARCH_SETUP = auto()
    ADVANCED_SEARCH_VIEWING = auto()
    LIKES_VIEWING = auto()
    EDIT_PHOTO = auto()
    VIEW_STATS = auto()  # Новое состояние для просмотра статистики
    DELETE_PHOTO = auto()  # Новое состояние для удаления конкретного фото

# -------- Helpers --------
def _valid_nickname(nick: str) -> bool:
    nick = nick.strip()
    if not (2 <= len(nick) <= 50):
        return False
    # Разрешаем буквы (в т.ч. кириллицу), цифры, пробел, точку, дефис, подчёркивание
    # Запрещаем явные служебные символы
    forbidden = set('@#$%^&*()+={}[]|\\:;"\'<>/?')
    return not any(ch in forbidden for ch in nick)

def _parse_winrate(winrate_text: str) -> Optional[int]:
    text = (winrate_text or "").strip()
    if not text.isdigit():
        return None
    winrate = int(text)
    if 0 <= winrate <= 100:
        return winrate
    return None

def _matches_rank(user: db.UserProfile, selected_ranks: set) -> bool:
    """Проверяет, соответствует ли ранг пользователя выбранным рангам"""
    if "Мифический (любой)" in selected_ranks and user.rank == "Мифический":
        return True
    if user.mythic_rank in selected_ranks:
        return True
    if user.rank in selected_ranks:
        return True
    return False

async def get_user_profile_text(user_data: db.UserProfile, short: bool = False) -> str:
    if not user_data:
        return "Ошибка: данные профиля не найдены"
    
    about_text = user_data.about
    if short and len(about_text) > MAX_ABOUT_LENGTH:
        about_text = about_text[:MAX_ABOUT_LENGTH] + "..."
    
    profile_text = (
        f"👤 *Ник:* {user_data.nickname}\n"
        f"📊 *Winrate:* {user_data.winrate}%\n"
        f"⚔️ *Линия:* {user_data.line}\n"
        f"🏆 *Ранг:* {user_data.rank}"
    )
    if user_data.mythic_rank:
        profile_text += f" ({user_data.mythic_rank})"
    profile_text += (
        f"\n🎯 *Цель:* {user_data.goal}\n"
        f"📝 *О себе:* {about_text}"
    )
    # Добавляем информацию о количестве фотографий
    if user_data.photo_ids and len(user_data.photo_ids) > 0:
        profile_text += f"\n🖼️ *Фото:* {len(user_data.photo_ids)}"
    return profile_text

async def send_profile_card(bot: Bot, chat_id: int, user_data: db.UserProfile, prefix: str = "", short: bool = False) -> None:
    """Отправляет профиль в указанный чат"""
    if not user_data:
        await bot.send_message(chat_id=chat_id, text="Ошибка: данные профиля не найдены")
        return
    
    try:
        text_md = await get_user_profile_text(user_data, short)
        caption = f"{prefix}{text_md}"
        
        # Проверяем, есть ли у пользователя фотографии
        if user_data.photo_ids and len(user_data.photo_ids) > 0:
            # Отправляем первую фотографию с подписью
            await bot.send_photo(
                chat_id=chat_id,
                photo=user_data.photo_ids[0],
                caption=caption,
                parse_mode="Markdown"
            )
            
            # Если есть дополнительные фотографии, отправляем их отдельными сообщениями
            for photo_id in user_data.photo_ids[1:]:
                await bot.send_photo(
                    chat_id=chat_id,
                    photo=photo_id
                )
        else:
            await bot.send_message(
                chat_id=chat_id,
                text=caption,
                parse_mode="Markdown"
            )
    except TelegramError as e:
        logger.exception(f"Error sending profile card to {chat_id}")
        try:
            await bot.send_message(
                chat_id=chat_id,
                text="Не удалось загрузить анкету (возможно, фото устарело)."
            )
        except TelegramError:
            logger.exception(f"Failed to send error message to {chat_id}")

async def show_profile_card(update: Update, keyboard, user_data: db.UserProfile, prefix: str = "", short: bool = False) -> None:
    """Отображает профиль в текущем чате"""
    if not update or not update.message or not user_data:
        return
    
    try:
        text_md = await get_user_profile_text(user_data, short)
        caption = f"{prefix}{text_md}"
        
        # Проверяем, есть ли у пользователя фотографии
        if user_data.photo_ids and len(user_data.photo_ids) > 0:
            # Отправляем первую фотографию с подписью и клавиатурой
            await update.message.reply_photo(
                photo=user_data.photo_ids[0],
                caption=caption,
                reply_markup=keyboard,
                parse_mode="Markdown"
            )
            
            # Если есть дополнительные фотографии, отправляем их отдельными сообщениями
            for photo_id in user_data.photo_ids[1:]:
                await update.message.reply_photo(
                    photo=photo_id,
                    reply_markup=ReplyKeyboardRemove()
                )
        else:
            await update.message.reply_text(
                caption,
                reply_markup=keyboard,
                parse_mode="Markdown"
            )
    except Exception as e:
        logger.exception("Error showing profile card")
        await update.message.reply_text(
            "Не удалось загрузить анкету (возможно, фото устарело)."
        )
        await update.message.reply_text(
            caption if 'caption' in locals() else text_md,
            reply_markup=keyboard,
            parse_mode="Markdown"
        )

async def show_main_menu(update: Update, text: str) -> None:
    if not update or not update.message:
        return
    reply_keyboard = [
        ["🚀 Быстрый поиск", "⚙️ Поиск тиммейта"],
        ["👤 Моя анкета", "❤️ Понравился"],
    ]
    await update.message.reply_text(
        text,
        reply_markup=ReplyKeyboardMarkup(reply_keyboard, resize_keyboard=True)
    )

# -------- Entry / Persistence --------
def build_application() -> Application:
    # Persistence to allow resume after restart without /start
    persistence = PicklePersistence(filepath="bot_data.pkl")
    app = Application.builder().token(TELEGRAM_TOKEN).persistence(persistence).build()

    # Conversation handler
    conv = ConversationHandler(
        name="main_conv",
        persistent=True,
        entry_points=[
            CommandHandler("start", start_command),
        ],
        states={
            States.SELECTING_ACTION.value: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, selecting_action_handler),
            ],
            States.GET_NICKNAME.value: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_nickname_input),
            ],
            States.GET_WINRATE.value: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_winrate),
            ],
            States.GET_LINE.value: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_line),
            ],
            States.GET_RANK.value: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_rank),
            ],
            States.GET_MYTHIC_RANK.value: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_mythic_rank),
            ],
            States.GET_GOAL.value: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_goal_choice),
            ],
            States.GET_ABOUT.value: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_about),
            ],
            States.GET_PHOTO.value: [
                MessageHandler(filters.PHOTO, get_photo),
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_photo),
            ],
            States.MAIN_MENU.value: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, main_menu_handler),
            ],
            States.MY_PROFILE.value: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_my_profile_action),
            ],
            States.EDIT_PROFILE_CHOICE.value: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_edit_profile_choice),
            ],
            States.EDIT_PROFILE_INPUT.value: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, process_edit_profile_input),
            ],
            States.EDIT_MYTHIC_RANK.value: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_mythic_rank),
            ],
            States.QUICK_SEARCH_SETUP.value: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_quick_search_setup),
            ],
            States.QUICK_SEARCH_VIEWING.value: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_profile_view_action),
            ],
            States.ADVANCED_SEARCH_SETUP.value: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_advanced_search_setup),
            ],
            States.ADVANCED_SEARCH_VIEWING.value: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_profile_view_action),
            ],
            States.LIKES_VIEWING.value: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_likes_viewing_action),
            ],
            States.EDIT_PHOTO.value: [
                MessageHandler(filters.PHOTO, handle_edit_photo),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_edit_photo),
            ],
            States.DELETE_PHOTO.value: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_delete_photo),
            ],
            States.DELETE_CONFIRM.value: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_delete_confirm),
            ],
            States.VIEW_STATS.value: [  # Добавлено новое состояние
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_stats_view),
            ],
        },
        fallbacks=[
            # fallback: если бот рестартанулся — позволяем сразу попасть в меню по кнопкам
            MessageHandler(filters.Regex("^(🚀 Быстрый поиск|⚙️ Поиск тиммейта|👤 Моя анкета|❤️ Понравился)$"), direct_menu_shortcut),
        ],
        allow_reentry=True,
    )

    # Глобальный хэндлер для обновления активности на любой текст (не команды)
    app.add_handler(conv)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, heartbeat))
    return app

# -------- Handlers --------
async def heartbeat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обновляем активность на любой текст, чтобы окно '3 минуты' было точнее"""
    try:
        if update and update.effective_user:
            db.update_user_activity(update.effective_user.id)
    except Exception:
        logger.exception("heartbeat failed")

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    if not user:
        return ConversationHandler.END

    db.check_database()
    user_profile = db.get_user_by_id(user.id)
    if user_profile:
        db.update_user_activity(user.id)
        await show_main_menu(update, "Ого, привет! Рад снова тебя видеть! 😊 Чем займёмся сегодня?")
        return States.MAIN_MENU.value
    else:
        # начало мастера регистрации
        if context and context.user_data is not None:
            context.user_data.clear()
        await update.message.reply_text(
            "Привет-привет! Я Sil, твой личный помощник в мире MLBB! 🎮\n\nДавай знакомиться! Как тебя зовут в игре? Напиши свой никнейм:",
            reply_markup=ReplyKeyboardMarkup([["❌ Отмена"]], resize_keyboard=True)  # Убрали кнопку "Назад"
        )
        return States.GET_NICKNAME.value

async def direct_menu_shortcut(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Позволяет сразу нажимать кнопки главного меню после рестарта процесса"""
    text = update.message.text
    if text == "🚀 Быстрый поиск":
        if context and context.user_data is not None:
            context.user_data['selected_ranks'] = set()
            context.user_data.setdefault('active_window', DEFAULT_QUICK_SEARCH_ACTIVE_WINDOW)
        await quick_search_setup_menu(update, context)
        return States.QUICK_SEARCH_SETUP.value
    if text == "⚙️ Поиск тиммейта":
        if context and context.user_data is not None:
            context.user_data['adv_filters'] = {'ranks': set(), 'winrate': None, 'photo': False}
        await advanced_search_setup_menu(update, context)
        return States.ADVANCED_SEARCH_SETUP.value
    if text == "👤 Моя анкета":
        return await show_my_profile(update, context)
    if text == "❤️ Понравился":
        return await show_likes_start(update, context)
    # default: вернуть в меню
    await show_main_menu(update, "Выбери действие:")
    return States.MAIN_MENU.value

async def selecting_action_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    # используется на самом раннем экране, можно просто отдать меню
    await show_main_menu(update, "Выбери действие:")
    return States.MAIN_MENU.value

# ---- Registration flow ----
async def handle_nickname_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = (update.message.text or "").strip()
    
    # Убрали кнопку "Назад", оставили только "Отмена"
    if text == "❌ Отмена":
        await update.message.reply_text(
            "Окей, отменили регистрацию! Если передумаешь — просто напиши /start 😊",
            reply_markup=ReplyKeyboardMarkup([["/start"]], resize_keyboard=True)
        )
        return ConversationHandler.END

    if not _valid_nickname(text):
        await update.message.reply_text(
            "Ой, кажется, в нике есть что-то лишнее! 😅 Используй только буквы, цифры и символы ._-\nПопробуй ещё раз:",
            reply_markup=ReplyKeyboardMarkup([["❌ Отмена"]], resize_keyboard=True)
        )
        return States.GET_NICKNAME.value

    context.user_data['profile_data'] = context.user_data.get('profile_data', {})
    context.user_data['profile_data']['nickname'] = text

    await update.message.reply_text(
        f"Отлично, {text}! 👍 Теперь расскажи мне о твоём винрейте. Введи число от 0 до 100.\n\n💡 Если у тебя 50.6% — округли до 51!",
        reply_markup=ReplyKeyboardMarkup([["⬅️ Назад", "❌ Отмена"]], resize_keyboard=True)
    )
    return States.GET_WINRATE.value

async def get_winrate(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = (update.message.text or "").strip()
    if text == "/start":
        return await start_command(update, context)

    if text == "⬅️ Назад":
        await update.message.reply_text(
            "Давай вернёмся к никнейму! Как тебя зовут в игре?",
            reply_markup=ReplyKeyboardMarkup([["❌ Отмена"]], resize_keyboard=True)
        )
        return States.GET_NICKNAME.value
    if text == "❌ Отмена":
        await update.message.reply_text(
            "Жаль, что передумал(а)! 😔 Если захочешь создать анкету — просто напиши /start",
            reply_markup=ReplyKeyboardMarkup([["/start"]], resize_keyboard=True)
        )
        return ConversationHandler.END

    winrate = _parse_winrate(text)
    if winrate is None:
        await update.message.reply_text(
            "Эй, я просил только цифры от 0 до 100! 😊 Никаких букв, точек и символов — только целое число.\n\n💡 Если у тебя 50.6% — округли до 51!\nПопробуй ещё раз:",
            reply_markup=ReplyKeyboardMarkup([["⬅️ Назад", "❌ Отмена"]], resize_keyboard=True)
        )
        return States.GET_WINRATE.value

    context.user_data['profile_data']['winrate'] = winrate
    context.user_data['selected_lines'] = set()
    await line_selection_menu(update, context)
    return States.GET_LINE.value

async def line_selection_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    selected = context.user_data.get('selected_lines', set())
    keyboard, row = [], []
    for line in LINES:
        label = f"✅ {line}" if line in selected else line
        row.append(label)
        if len(row) == 2:
            keyboard.append(row); row = []
    if row: keyboard.append(row)
    keyboard += [["▶️ Далее", "❌ Отмена"], ["⬅️ Назад"]]
    await update.message.reply_text(
        "Теперь выбери свою роль/линию! Можно выбрать несколько вариантов 😊",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )

async def get_line(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    choice = update.message.text
    if choice == "⬅️ Назад":
        await update.message.reply_text(
            f"Вернёмся к винрейту! Твой винрейт: {context.user_data['profile_data']['winrate']}%",
            reply_markup=ReplyKeyboardMarkup([["⬅️ Назад", "❌ Отмена"]], resize_keyboard=True)
        )
        return States.GET_WINRATE.value
    if choice == "❌ Отмена":
        await update.message.reply_text(
            "Жаль, что передумал(а)! 😔 Если захочешь создать анкету — просто напиши /start",
            reply_markup=ReplyKeyboardMarkup([["/start"]], resize_keyboard=True)
        )
        return ConversationHandler.END

    if choice == "▶️ Далее":
        selected = context.user_data.get('selected_lines', set())
        if not selected:
            await update.message.reply_text(
                "Эй, выбери хотя бы одну роль! Я не могу прочитать твои мысли 😜",
                reply_markup=ReplyKeyboardMarkup([["▶️ Далее", "❌ Отмена"], ["⬅️ Назад"]], resize_keyboard=True)
            )
            return States.GET_LINE.value
        
        # Проверяем, если выбраны все линии кроме "Везде", заменяем на "Везде"
        all_lines_selected = all(line in selected for line in LINES if line != "Везде")
        if all_lines_selected:
            selected.clear()
            selected.add("Везде")
        
        line_value = "Везде" if "Везде" in selected else ", ".join(sorted(selected))
        context.user_data['profile_data']['line'] = line_value
        await go_to_rank_step(update, context)
        return States.GET_RANK.value

    clean = choice.replace("✅ ", "")
    if clean in LINES:
        selected = context.user_data.get('selected_lines', set())
        if clean == "Везде":
            # Если выбрано "Везде", очищаем все остальные линии
            selected.clear()
            selected.add("Везде")
        else:
            # Если выбрана конкретная линия
            if "Везде" in selected:
                selected.remove("Везде")
            if clean in selected:
                selected.remove(clean)
            else:
                selected.add(clean)
            
            # Проверяем, если выбраны все линии кроме "Везде", заменяем на "Везде"
            all_lines_selected = all(line in selected for line in LINES if line != "Везде")
            if all_lines_selected:
                selected.clear()
                selected.add("Везде")
        
        context.user_data['selected_lines'] = selected
        # Обновляем меню после выбора
        await line_selection_menu(update, context)
        return States.GET_LINE.value

    await line_selection_menu(update, context)
    return States.GET_LINE.value

async def go_to_rank_step(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    keyboard = [RANKS[:3], RANKS[3:6], RANKS[6:], ["❌ Отмена"], ["⬅️ Назад"]]
    await update.message.reply_text(
        "Отлично! Теперь расскажи, какой у тебя ранг? 🏆 Не стесняйся, я никому не расскажу! 😜",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )

async def get_rank(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    choice = update.message.text
    if choice == "⬅️ Назад":
        await line_selection_menu(update, context)
        return States.GET_LINE.value
    if choice == "❌ Отмена":
        await update.message.reply_text(
            "Жаль, что передумал(а)! 😔 Если захочешь создать анкету — просто напиши /start",
            reply_markup=ReplyKeyboardMarkup([["/start"]], resize_keyboard=True)
        )
        return ConversationHandler.END

    if choice not in RANKS:
        await update.message.reply_text(
            "Эй, выбери ранг из кнопок! Я не телепат 😅",
            reply_markup=ReplyKeyboardMarkup([RANKS[:3], RANKS[3:6], RANKS[6:], ["❌ Отмена"], ["⬅️ Назад"]], resize_keyboard=True)
        )
        return States.GET_RANK.value

    context.user_data['profile_data']['rank'] = choice
    if choice == "Мифический":
        keyboard = [MYTHIC_RANKS[:2], MYTHIC_RANKS[2:], ["❌ Отмена"], ["⬅️ Назад"]]
        await update.message.reply_text(
            "Ого, мифический ранг! 👑 Уточни, какой именно:",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        )
        return States.GET_MYTHIC_RANK.value
    else:
        context.user_data['profile_data']['mythic_rank'] = None
        return await show_goal_menu(update, context)

async def get_mythic_rank(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    choice = update.message.text
    if choice == "⬅️ Назад":
        await go_to_rank_step(update, context)
        return States.GET_RANK.value
    if choice == "❌ Отмена":
        await update.message.reply_text(
            "Жаль, что передумал(а)! 😔 Если захочешь создать анкету — просто напиши /start",
            reply_markup=ReplyKeyboardMarkup([["/start"]], resize_keyboard=True)
        )
        return ConversationHandler.END

    if choice not in MYTHIC_RANKS:
        keyboard = [MYTHIC_RANKS[:2], MYTHIC_RANKS[2:], ["❌ Отмена"], ["⬅️ Назад"]]
        await update.message.reply_text(
            "Выбери один из мифических рангов из кнопок! 👑",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        )
        return States.GET_MYTHIC_RANK.value

    context.user_data['profile_data']['mythic_rank'] = choice
    return await show_goal_menu(update, context)

async def show_goal_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    keyboard = [GOALS[:2], [GOALS[2]], ["❌ Отмена"], ["⬅️ Назад"]]
    await update.message.reply_text(
        "Отлично! Теперь расскажи, чего ты хочешь достичь в игре? 🎯",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )
    return States.GET_GOAL.value

async def handle_goal_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    choice = update.message.text
    if choice == "⬅️ Назад":
        # вернуться к рангу/мифическому
        if context.user_data.get('profile_data', {}).get('rank') == "Мифический":
            keyboard = [MYTHIC_RANKS[:2], MYTHIC_RANKS[2:], ["❌ Отмена"], ["⬅️ Назад"]]
            await update.message.reply_text(
                "Вернёмся к выбору мифического ранга 👑",
                reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            )
            return States.GET_MYTHIC_RANK.value
        else:
            await go_to_rank_step(update, context)
            return States.GET_RANK.value

    if choice == "❌ Отмена":
        await update.message.reply_text(
            "Жаль, что передумал(а)! 😔 Если захочешь создать анкету — просто напиши /start",
            reply_markup=ReplyKeyboardMarkup([["/start"]], resize_keyboard=True)
        )
        return ConversationHandler.END

    if choice not in GOALS:
        await update.message.reply_text(
            "Выбери цель из кнопок! Я не умею читать мысли 😜",
            reply_markup=ReplyKeyboardMarkup([GOALS[:2], [GOALS[2]], ["❌ Отмена"], ["⬅️ Назад"]], resize_keyboard=True)
        )
        return States.GET_GOAL.value

    context.user_data['profile_data']['goal'] = choice
    await update.message.reply_text(
        "Расскажи немного о себе (до 500 символов) или нажми ➡️ Далее, чтобы пропустить. ✍️\n\nХочешь, я могу придумать что-нибудь за тебя? 😄",
        reply_markup=ReplyKeyboardMarkup([["➡️ Далее", "❌ Отмена"], ["⬅️ Назад"]], resize_keyboard=True)
    )
    return States.GET_ABOUT.value

async def get_about(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    choice = update.message.text
    if choice == "⬅️ Назад":
        keyboard = [GOALS[:2], [GOALS[2]], ["❌ Отмена"], ["⬅️ Назад"]]
        await update.message.reply_text(
            "Вернёмся к выбору цели! 🎯",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        )
        return States.GET_GOAL.value
    if choice == "❌ Отмена":
        await update.message.reply_text(
            "Жаль, что передумал(а)! 😔 Если захочешь создать анкету — просто напиши /start",
            reply_markup=ReplyKeyboardMarkup([["/start"]], resize_keyboard=True)
        )
        return ConversationHandler.END

    if choice == "➡️ Далее":
        context.user_data['profile_data']['about'] = "Не указано"
    else:
        if len(choice) > 500:
            await update.message.reply_text(
                "Ого, многовато букв! 😅 Уложись в 500 символов, пожалуйста!",
                reply_markup=ReplyKeyboardMarkup([["➡️ Далее", "❌ Отмена"], ["⬅️ Назад"]], resize_keyboard=True)
            )
            return States.GET_ABOUT.value
        context.user_data['profile_data']['about'] = choice

    await update.message.reply_text(
        "Последний шаг — фото профиля (необязательно). Отправь фото или нажми «➡️ Завершить без фото». 📷\n\nХочешь, я могу сгенерировать крутую аватарку за тебя? 😎",
        reply_markup=ReplyKeyboardMarkup([["📷 Добавить фото", "➡️ Завершить без фото"], ["❌ Отмена"], ["⬅️ Назад"]], resize_keyboard=True)
    )
    return States.GET_PHOTO.value

async def get_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    # фото
    if update.message and update.message.photo:
        # Инициализируем список фотографий, если его еще нет
        context.user_data.setdefault('profile_data', {})['photo_ids'] = []
        
        # Добавляем ID фотографии в список
        photo_id = update.message.photo[-1].file_id
        context.user_data['profile_data']['photo_ids'].append(photo_id)
        
        # Проверяем, достигли ли максимального количества фотографий
        if len(context.user_data['profile_data']['photo_ids']) >= MAX_PHOTOS:
            await update.message.reply_text(
                f"Вау, ты загрузил(а) уже {MAX_PHOTOS} фото! Это максимум! 📸",
                reply_markup=ReplyKeyboardMarkup([["➡️ Завершить", "❌ Отмена"], ["⬅️ Назад"]], resize_keyboard=True)
            )
        else:
            await update.message.reply_text(
                f"Классное фото! 📸 Ещё можешь добавить {MAX_PHOTOS - len(context.user_data['profile_data']['photo_ids'])} фото или завершить.",
                reply_markup=ReplyKeyboardMarkup([["📷 Добавить еще фото", "➡️ Завершить"], ["❌ Отмена"], ["⬅️ Назад"]], resize_keyboard=True)
            )
        return States.GET_PHOTO.value

    # текстовые кнопки
    text = update.message.text if update.message else ""
    if text == "⬅️ Назад":
        await update.message.reply_text(
            "Вернёмся к рассказу о себе! ✍️",
            reply_markup=ReplyKeyboardMarkup([["➡️ Далее", "❌ Отмена"], ["⬅️ Назад"]], resize_keyboard=True)
        )
        return States.GET_ABOUT.value

    if text == "❌ Отмена":
        await update.message.reply_text(
            "Жаль, что передумал(а)! 😔 Если захочешь создать анкету — просто напиши /start",
            reply_markup=ReplyKeyboardMarkup([["/start"]], resize_keyboard=True)
        )
        return ConversationHandler.END

    if text == "➡️ Завершить" or text == "➡️ Завершить без фото":
        # Если нет фотографий, устанавливаем пустой список
        context.user_data.setdefault('profile_data', {})['photo_ids'] = []
        return await save_profile(update, context)

    if text == "📷 Добавить фото" or text == "📷 Добавить еще фото":
        await update.message.reply_text(
            "Отправь фото (из Галереи) или нажми «➡️ Завершить». 📷",
            reply_markup=ReplyKeyboardMarkup([["➡️ Завершить", "❌ Отмена"], ["⬅️ Назад"]], resize_keyboard=True)
        )
        return States.GET_PHOTO.value

    # иначе повторим приглашение
    await update.message.reply_text(
        "Отправь фото или нажми «➡️ Завершить». 📷",
        reply_markup=ReplyKeyboardMarkup([["➡️ Завершить", "❌ Отмена"], ["⬅️ Назад"]], resize_keyboard=True)
    )
    return States.GET_PHOTO.value

async def save_profile(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    data = context.user_data.get('profile_data', {})
    data.update({
        "user_id": user.id,
        "telegram_username": user.username,
        "last_active_timestamp": int(time.time())
    })
    
    # Убедимся, что поле photo_ids существует
    data.setdefault('photo_ids', [])
    
    ok = db.create_user_profile(data)
    if not ok:
        await update.message.reply_text(
            "Ой, что-то пошло не так при сохранении анкеты! 😓 Попробуй позже, пожалуйста!",
            reply_markup=ReplyKeyboardMarkup([["/start"]], resize_keyboard=True)
        )
        return ConversationHandler.END
    if context and context.user_data is not None:
        context.user_data.clear()
    await show_main_menu(update, "Ура! Твоя анкета готова! 🎉 Теперь можешь искать тиммейтов или ждать, когда найдут тебя!")
    return States.MAIN_MENU.value

# ---- Main menu ----
async def main_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    user_profile = db.get_user_by_id(user_id)
    if not user_profile:
        await update.message.reply_text(
            "Сначала создай анкету! Нажми /start, и мы всё сделаем вместе! 😊",
            reply_markup=ReplyKeyboardMarkup([["/start"]], resize_keyboard=True)
        )
        return await start_command(update, context)

    db.update_user_activity(user_id)

    text = update.message.text
    if text == "🚀 Быстрый поиск":
        context.user_data['selected_ranks'] = set()
        context.user_data.setdefault('active_window', DEFAULT_QUICK_SEARCH_ACTIVE_WINDOW)
        await quick_search_setup_menu(update, context)
        return States.QUICK_SEARCH_SETUP.value

    if text == "⚙️ Поиск тиммейта":
        context.user_data['adv_filters'] = {'ranks': set(), 'winrate': None, 'photo': False}
        await advanced_search_setup_menu(update, context)
        return States.ADVANCED_SEARCH_SETUP.value

    if text == "👤 Моя анкета":
        return await show_my_profile(update, context)

    if text == "❤️ Понравился":
        return await show_likes_start(update, context)

    await show_main_menu(update, "Выбери действие:")
    return States.MAIN_MENU.value

# ---- Quick search ----
async def quick_search_setup_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    selected_ranks = context.user_data.get('selected_ranks', set())
    active_window = context.user_data.get('active_window', DEFAULT_QUICK_SEARCH_ACTIVE_WINDOW)
    
    # Определяем текст для выбранного окна активности
    window_text = "3 минуты" if active_window == 3 * 60 else "5 минут" if active_window == 5 * 60 else "10 минут"
    
    keyboard, row = [], []
    for rank in ALL_RANKS:
        label = f"✅ {rank}" if rank in selected_ranks else rank
        row.append(label)
        if len(row) == 2:
            keyboard.append(row); row = []
    if row: keyboard.append(row)
    keyboard += [["⏱️ Активность: " + window_text], ["▶️ Начать просмотр"], ["⏹️ Вернуться в меню"]]
    await update.message.reply_text(
        "Быстрый поиск: выбери ранги (1 или несколько). Покажу только тех, кто был активен в выбранное время. ⏱️",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )

async def handle_quick_search_setup(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    choice = update.message.text
    if choice == "⏹️ Вернуться в меню":
        await show_main_menu(update, "Окей, вернулись в меню. 😊")
        return States.MAIN_MENU.value

    if choice == "▶️ Начать просмотр":
        selected = context.user_data.get('selected_ranks', set())
        if not selected:
            await update.message.reply_text(
                "Эй, выбери хотя бы один ранг! 🏆",
                reply_markup=ReplyKeyboardMarkup([["▶️ Начать просмотр"], ["⏹️ Вернуться в меню"]], resize_keyboard=True)
            )
            return States.QUICK_SEARCH_SETUP.value

        try:
            active_window = context.user_data.get('active_window', DEFAULT_QUICK_SEARCH_ACTIVE_WINDOW)
            active_users = db.get_active_users(exclude_user_id=update.effective_user.id, max_age_seconds=active_window)
        except Exception:
            logger.exception("get_active_users failed")
            await update.message.reply_text(
                "Ой, что-то пошло не так при поиске игроков! 😓 Попробуй позже, пожалуйста!",
                reply_markup=ReplyKeyboardMarkup([["▶️ Начать просмотр"], ["⏹️ Вернуться в меню"]], resize_keyboard=True)
            )
            return States.QUICK_SEARCH_SETUP.value

        filtered = []
        for u in active_users:
            if _matches_rank(u, selected):
                filtered.append(u)

        if not filtered:
            await update.message.reply_text(
                "Пока никого подходящего нет онлайн! 😔 Попробуй позже или расширь критерии поиска.",
                reply_markup=ReplyKeyboardMarkup([["▶️ Начать просмотр"], ["⏹️ Вернуться в меню"]], resize_keyboard=True)
            )
            return States.QUICK_SEARCH_SETUP.value

        random.shuffle(filtered)
        context.user_data['search_results'] = [p.to_dict() for p in filtered]
        context.user_data['current_index'] = 0
        context.user_data['view_type'] = 'quick'
        return await show_next_profile(update, context)

    # Обработка выбора окна активности
    if choice.startswith("⏱️ Активность:"):
        # Циклическое переключение между вариантами
        current_window = context.user_data.get('active_window', DEFAULT_QUICK_SEARCH_ACTIVE_WINDOW)
        if current_window == 3 * 60:
            context.user_data['active_window'] = 5 * 60
        elif current_window == 5 * 60:
            context.user_data['active_window'] = 10 * 60
        else:
            context.user_data['active_window'] = 3 * 60
        await quick_search_setup_menu(update, context)
        return States.QUICK_SEARCH_SETUP.value

    clean = choice.replace("✅ ", "")
    if clean in ALL_RANKS:
        selected = context.user_data.get('selected_ranks', set())
        
        # Логика для мифических рангов
        if clean == "Мифический (любой)":
            # Если выбираем "Мифический (любой)", убираем все конкретные мифические ранги
            for mythic_rank in MYTHIC_RANKS:
                if mythic_rank in selected:
                    selected.remove(mythic_rank)
            selected.add(clean)
        elif clean in MYTHIC_RANKS:
            # Если выбираем конкретный мифический ранг, убираем "Мифический (любой)"
            if "Мифический (любой)" in selected:
                selected.remove("Мифический (любой)")
            if clean in selected:
                selected.remove(clean)
            else:
                selected.add(clean)
        else:
            # Для обычных рангов просто переключаем выбор
            if clean in selected:
                selected.remove(clean)
            else:
                selected.add(clean)
        
        # Проверяем, если выбраны все мифические ранги, заменяем их на "Мифический (любой)"
        all_mythic_selected = all(rank in selected for rank in MYTHIC_RANKS)
        if all_mythic_selected and "Мифический (любой)" not in selected:
            for mythic_rank in MYTHIC_RANKS:
                selected.remove(mythic_rank)
            selected.add("Мифический (любой)")
        
        context.user_data['selected_ranks'] = selected
        await quick_search_setup_menu(update, context)
        return States.QUICK_SEARCH_SETUP.value

    return States.QUICK_SEARCH_SETUP.value

# ---- Advanced search ----
async def advanced_search_setup_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, sub_menu: Optional[str] = None) -> None:
    filters_map = context.user_data.get('adv_filters', {'ranks': set(), 'winrate': None, 'photo': False})
    if sub_menu == 'ranks':
        selected = filters_map.get('ranks', set())
        keyboard, row = [], []
        for rank in ALL_RANKS:
            label = f"✅ {rank}" if rank in selected else rank
            row.append(label)
            if len(row) == 2:
                keyboard.append(row); row = []
        if row: keyboard.append(row)
        keyboard.append(["↩️ Назад к фильтрам"])
        await update.message.reply_text(
            "Выбери интересующие ранги:",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        )
        return

    if sub_menu == 'winrate':
        keyboard = [[x] for x in WINRATE_FILTERS] + [["↩️ Назад к фильтрам"]]
        await update.message.reply_text(
            "Выбери фильтр Winrate относительно твоего WR:",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        )
        return

    ranks_text = f"Ранги ({len(filters_map.get('ranks', set()))} выбрано)"
    wr_text = f"Winrate ({filters_map.get('winrate', 'Неважно')})"
    photo_text = "Фото (Только с фото)" if filters_map.get('photo') else "Фото (Неважно)"
    keyboard = [[ranks_text], [wr_text], [photo_text], ["▶️ Начать просмотр"], ["⏹️ Вернуться в меню"]]
    await update.message.reply_text(
        "Настрой фильтры:",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )

async def handle_advanced_search_setup(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    choice = update.message.text
    filters_map = context.user_data.get('adv_filters', {'ranks': set(), 'winrate': None, 'photo': False})

    if choice == "⏹️ Вернуться в меню":
        await show_main_menu(update, "Окей, вернулись в меню. 😊")
        return States.MAIN_MENU.value

    if choice.startswith("Ранги"):
        await advanced_search_setup_menu(update, context, sub_menu='ranks')
        return States.ADVANCED_SEARCH_SETUP.value

    if choice.startswith("Winrate"):
        await advanced_search_setup_menu(update, context, sub_menu='winrate')
        return States.ADVANCED_SEARCH_SETUP.value

    if choice.startswith("Фото"):
        filters_map['photo'] = not filters_map.get('photo', False)
        context.user_data['adv_filters'] = filters_map
        await advanced_search_setup_menu(update, context)
        return States.ADVANCED_SEARCH_SETUP.value

    if choice == "↩️ Назад к фильтрам":
        await advanced_search_setup_menu(update, context)
        return States.ADVANCED_SEARCH_SETUP.value

    if choice in WINRATE_FILTERS:
        filters_map['winrate'] = choice
        context.user_data['adv_filters'] = filters_map
        await advanced_search_setup_menu(update, context)
        return States.ADVANCED_SEARCH_SETUP.value

    if choice.replace("✅ ", "") in ALL_RANKS:
        rank = choice.replace("✅ ", "")
        selected = filters_map.get('ranks', set())
        
        # Логика для мифических рангов
        if rank == "Мифический (любой)":
            # Если выбираем "Мифический (любой)", убираем все конкретные мифические ранги
            for mythic_rank in MYTHIC_RANKS:
                if mythic_rank in selected:
                    selected.remove(mythic_rank)
            selected.add(rank)
        elif rank in MYTHIC_RANKS:
            # Если выбираем конкретный мифический ранг, убираем "Мифический (любой)"
            if "Мифический (любой)" in selected:
                selected.remove("Мифический (любой)")
            if rank in selected:
                selected.remove(rank)
            else:
                selected.add(rank)
        else:
            # Для обычных рангов просто переключаем выбор
            if rank in selected:
                selected.remove(rank)
            else:
                selected.add(rank)
        
        # Проверяем, если выбраны все мифические ранги, заменяем их на "Мифический (любой)"
        all_mythic_selected = all(r in selected for r in MYTHIC_RANKS)
        if all_mythic_selected and "Мифический (любой)" not in selected:
            for mythic_rank in MYTHIC_RANKS:
                selected.remove(mythic_rank)
            selected.add("Мифический (любой)")
        
        filters_map['ranks'] = selected
        context.user_data['adv_filters'] = filters_map
        await advanced_search_setup_menu(update, context, sub_menu='ranks')
        return States.ADVANCED_SEARCH_SETUP.value

    if choice == "▶️ Начать просмотр":
        try:
            # В расширенном поиске не фильтруем по активности
            active_users = db.get_active_users(exclude_user_id=update.effective_user.id, max_age_seconds=None)
        except Exception:
            logger.exception("get_active_users failed")
            await update.message.reply_text(
                "Ой, что-то пошло не так при поиске игроков! 😓 Попробуй позже, пожалуйста!",
                reply_markup=ReplyKeyboardMarkup([["▶️ Начать просмотр"], ["⏹️ Вернуться в меню"]], resize_keyboard=True)
            )
            return States.ADVANCED_SEARCH_SETUP.value

        # фильтры
        if filters_map.get('ranks'):
            selected = filters_map['ranks']
            filtered_users = []
            for u in active_users:
                if _matches_rank(u, selected):
                    filtered_users.append(u)
            active_users = filtered_users
            
        if filters_map.get('photo'):
            active_users = [u for u in active_users if u.photo_ids and len(u.photo_ids) > 0]
        if filters_map.get('winrate') and filters_map['winrate'] != 'Неважно':
            me = db.get_user_by_id(update.effective_user.id)
            if me:
                my_wr = me.winrate
                percentage = int(filters_map['winrate'][3:-1])
                lower = my_wr * (1 - percentage / 100)
                upper = my_wr * (1 + percentage / 100)
                active_users = [u for u in active_users if lower <= u.winrate <= upper]

        if not active_users:
            await update.message.reply_text(
                "По твоим фильтрам никого не нашлось! 😔 Измени параметры и попробуй снова.",
                reply_markup=ReplyKeyboardMarkup([["▶️ Начать просмотр"], ["⏹️ Вернуться в меню"]], resize_keyboard=True)
            )
            return States.ADVANCED_SEARCH_SETUP.value

        random.shuffle(active_users)
        context.user_data['search_results'] = [p.to_dict() for p in active_users]
        context.user_data['current_index'] = 0
        context.user_data['view_type'] = 'advanced'
        return await show_next_profile(update, context)

    return States.ADVANCED_SEARCH_SETUP.value

# ---- Browsing profiles ----
async def show_next_profile(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    profiles = context.user_data.get('search_results', [])
    idx = context.user_data.get('current_index', 0)
    view_type = context.user_data.get('view_type')
    state_to_return = States.QUICK_SEARCH_VIEWING.value if view_type == 'quick' else States.ADVANCED_SEARCH_VIEWING.value

    if idx >= len(profiles):
        keyboard = ReplyKeyboardMarkup([["🔄 Начать поиск заново", "⚙️ Изменить критерии"], ["⬅️ В главное меню"]], resize_keyboard=True)
        await update.message.reply_text(
            "Это все анкеты по твоему запросу. 📋",
            reply_markup=keyboard
        )
        return state_to_return

    pdata = profiles[idx]
    profile = db.UserProfile(**pdata) if isinstance(pdata, dict) else pdata
    try:
        db.add_profile_view(update.effective_user.id, profile.user_id)
    except Exception:
        logger.exception("add_profile_view failed")

    keyboard = ReplyKeyboardMarkup([["❤️ Нравится", "👎 Следующий"], ["⏹️ Завершить поиск"]], resize_keyboard=True)
    await show_profile_card(update, keyboard, profile, short=True)  # Короткая версия для карточек
    context.user_data['current_viewed_profile'] = pdata
    context.user_data['current_index'] = idx + 1
    return state_to_return

async def handle_profile_view_action(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    choice = update.message.text
    view_type = context.user_data.get('view_type')
    state_to_return = States.QUICK_SEARCH_VIEWING.value if view_type == 'quick' else States.ADVANCED_SEARCH_VIEWING.value

    if choice == "⏹️ Завершить поиск":
        await show_main_menu(update, "Поиск завершён. До новых встреч! 👋")
        return States.MAIN_MENU.value

    if choice == "👎 Следующий":
        return await show_next_profile(update, context)

    if choice == "❤️ Нравится":
        current_profile = context.user_data.get('current_viewed_profile')
        if not current_profile:
            await update.message.reply_text(
                "Ой, что-то пошло не так! 😓 Попробуй следующий профиль.",
                reply_markup=ReplyKeyboardMarkup([["❤️ Нравится", "👎 Следующий"], ["⏹️ Завершить поиск"]], resize_keyboard=True)
            )
            return await show_next_profile(update, context)

        liked_user_id = current_profile['user_id'] if isinstance(current_profile, dict) else current_profile.user_id
        try:
            db.add_like(update.effective_user.id, liked_user_id)
            # проверим взаимность
            if db.has_like(liked_user_id, update.effective_user.id):
                # mutual!
                liked_user = db.get_user_by_id(liked_user_id)
                me = db.get_user_by_id(update.effective_user.id)
                if liked_user and me:
                    # Оба получают уведомление с контактом и анкетой
                    try:
                        await context.bot.send_message(
                            chat_id=liked_user_id,
                            text=f"🎉 У вас мэтч с {me.nickname}! Напиши ему/ей: @{me.telegram_username or 'скрыто'}"
                        )
                        # Отправляем анкету текущего пользователя
                        await send_profile_card(context.bot, liked_user_id, me, prefix="Его анкета:\n\n")
                        # Отправляем анкету того, кто лайкнул
                        await send_profile_card(context.bot, liked_user_id, liked_user, prefix="Твоя анкета:\n\n")
                    except TelegramError as e:
                        logger.exception(f"Failed to notify liked_user {liked_user_id}")
                        # Не прерываем поток, просто логируем ошибку

                    try:
                        await update.message.reply_text(
                            f"🎉 Мэтч! @{liked_user.telegram_username or 'скрыто'}",
                        )
                        # Отправляем анкету того, кто лайкнул
                        await show_profile_card(update, ReplyKeyboardMarkup([["👎 Следующий"], ["⏹️ Завершить поиск"]], resize_keyboard=True), liked_user, prefix="Анкета напарника:\n\n")
                        # Отправляем анкету текущего пользователя
                        await update.message.reply_text("Твоя анкета:", reply_markup=ReplyKeyboardRemove())
                        await show_profile_card(update, ReplyKeyboardRemove(), me)
                    except TelegramError as e:
                        logger.exception(f"Failed to notify me {update.effective_user.id}")
            else:
                await update.message.reply_text(
                    "Лайк отправлен! Если будет взаимно — я сразу сообщу. ❤️",
                    reply_markup=ReplyKeyboardMarkup([["❤️ Нравится", "👎 Следующий"], ["⏹️ Завершить поиск"]], resize_keyboard=True)
                )
        except Exception:
            logger.exception("add_like failed")
            await update.message.reply_text(
                "Не удалось отправить лайк! 😓 Попробуй позже.",
                reply_markup=ReplyKeyboardMarkup([["❤️ Нравится", "👎 Следующий"], ["⏹️ Завершить поиск"]], resize_keyboard=True)
            )
        return await show_next_profile(update, context)

    if choice == "🔄 Начать поиск заново":
        if view_type == 'quick':
            context.user_data['selected_ranks'] = set()
            context.user_data.setdefault('active_window', DEFAULT_QUICK_SEARCH_ACTIVE_WINDOW)
            await quick_search_setup_menu(update, context)
            return States.QUICK_SEARCH_SETUP.value
        else:
            context.user_data['adv_filters'] = {'ranks': set(), 'winrate': None, 'photo': False}
            await advanced_search_setup_menu(update, context)
            return States.ADVANCED_SEARCH_SETUP.value

    if choice == "⚙️ Изменить критерии":
        if view_type == 'quick':
            await quick_search_setup_menu(update, context)
            return States.QUICK_SEARCH_SETUP.value
        else:
            await advanced_search_setup_menu(update, context)
            return States.ADVANCED_SEARCH_SETUP.value

    return state_to_return

# ---- Likes viewing ----
async def show_likes_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    # users who liked me
    likers = db.get_users_who_liked_me(update.effective_user.id)
    # исключим взаимных (необязательно), но оставим — пользователю полезно видеть всех
    if not likers:
        await update.message.reply_text(
            "Пока никто не лайкнул твою анкету. Но не переживай! Твоя звезда обязательно взойдёт! ✨",
            reply_markup=ReplyKeyboardMarkup([["⬅️ В главное меню"]], resize_keyboard=True)
        )
        return States.MAIN_MENU.value

    context.user_data['likes_list'] = [u.to_dict() for u in likers]
    context.user_data['likes_index'] = 0
    return await show_next_like(update, context)

async def show_next_like(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lst = context.user_data.get('likes_list', [])
    idx = context.user_data.get('likes_index', 0)
    if idx >= len(lst):
        await update.message.reply_text(
            "Это все лайки на сейчас. ❤️",
            reply_markup=ReplyKeyboardMarkup([["⬅️ В главное меню"]], resize_keyboard=True)
        )
        return States.LIKES_VIEWING.value
    pdata = lst[idx]
    profile = db.UserProfile(**pdata)
    keyboard = ReplyKeyboardMarkup([["❤️ Взаимно", "👎 Пропустить"], ["⏹️ В меню"]], resize_keyboard=True)
    await show_profile_card(update, keyboard, profile, prefix="Тебя лайкнули! Посмотри анкету:\n\n")
    context.user_data['likes_index'] = idx + 1
    context.user_data['current_liker_id'] = profile.user_id
    return States.LIKES_VIEWING.value

async def handle_likes_viewing_action(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    choice = update.message.text
    if choice == "⏹️ В меню":
        await show_main_menu(update, "Вернулись в меню. 😊")
        return States.MAIN_MENU.value
    if choice == "👎 Пропустить":
        return await show_next_like(update, context)
    if choice == "❤️ Взаимно":
        liked_id = context.user_data.get('current_liker_id')
        if liked_id:
            db.add_like(update.effective_user.id, liked_id)
            # проверим взаимность (по идее, будет да)
            if db.has_like(liked_id, update.effective_user.id):
                liked_user = db.get_user_by_id(liked_id)
                me = db.get_user_by_id(update.effective_user.id)
                if liked_user and me:
                    try:
                        await context.bot.send_message(chat_id=liked_id, text=f"🎉 У вас мэтч с {me.nickname}! Напиши: @{me.telegram_username or 'скрыто'}")
                        # Отправляем анкету текущего пользователя
                        await send_profile_card(context.bot, liked_id, me, prefix="Твоя анкета:\n\n")
                        # Отправляем анкету того, кто лайкнул
                        await send_profile_card(context.bot, liked_id, liked_user, prefix="Анкета напарника:\n\n")
                        
                        await update.message.reply_text(f"🎉 Мэтч! Контакт: @{liked_user.telegram_username or 'скрыто'}")
                        # Отправляем анкету того, кто лайкнул
                        await show_profile_card(update, ReplyKeyboardMarkup([["👎 Пропустить"], ["⏹️ В меню"]], resize_keyboard=True), liked_user, prefix="Анкета напарника:\n\n")
                        # Отправляем анкету текущего пользователя
                        await update.message.reply_text("Твоя анкета:", reply_markup=ReplyKeyboardRemove())
                        await show_profile_card(update, ReplyKeyboardRemove(), me)
                    except TelegramError as e:
                        logger.exception("notify mutual in likes failed")
        return await show_next_like(update, context)
    # по умолчанию — следующий
    return await show_next_like(update, context)

# ---- My profile ----
async def show_my_profile(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = db.get_user_by_id(update.effective_user.id)
    if not user:
        await update.message.reply_text(
            "Твой профиль не найден! Давай создадим заново — нажми /start",
            reply_markup=ReplyKeyboardMarkup([["/start"]], resize_keyboard=True)
        )
        return States.SELECTING_ACTION.value
    keyboard = ReplyKeyboardMarkup([["✏️ Редактировать анкету", "📊 Статистика"], ["⬅️ В главное меню"]], resize_keyboard=True)
    await show_profile_card(update, keyboard, user, "Вот твоя анкета:\n\n")
    return States.MY_PROFILE.value

async def handle_my_profile_action(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    choice = update.message.text
    if choice == "⬅️ В главное меню":
        await show_main_menu(update, "Ок, что дальше? 😊")
        return States.MAIN_MENU.value
    if choice == "✏️ Редактировать анкету":
        keyboard = ReplyKeyboardMarkup([
            ["👤 Никнейм", "📊 Winrate"],
            ["⚔️ Линия", "🏆 Ранг"],
            ["🎯 Цель", "📝 О себе"],
            ["🖼️ Изменить фото", "🗑️ Удалить анкету"],
            ["⬅️ Назад"]
        ], resize_keyboard=True)
        await update.message.reply_text(
            "Выбери, что хочешь изменить:",
            reply_markup=keyboard
        )
        return States.EDIT_PROFILE_CHOICE.value
    if choice == "📊 Статистика":
        stats = db.get_user_stats(update.effective_user.id)
        txt = (
            f"📊 *Твоя статистика:*\n\n"
            f"👀 Просмотров: {stats.get('views', 0)}\n"
            f"❤️ Получено лайков: {stats.get('likes_received', 0)}\n"
            f"👍 Поставлено лайков: {stats.get('likes_given', 0)}\n"
            f"🤝 Взаимных лайков: {stats.get('mutual_likes', 0)}"
        )
        await update.message.reply_text(
            txt,
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardMarkup([["⬅️ Назад"]], resize_keyboard=True)
        )
        return States.VIEW_STATS.value  # Переходим в новое состояние
    return States.MY_PROFILE.value

# Новый обработчик для просмотра статистики
async def handle_stats_view(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    choice = update.message.text
    if choice == "⬅️ Назад":
        return await show_my_profile(update, context)
    # Если нажата любая другая кнопка, возвращаемся к просмотру профиля
    return await show_my_profile(update, context)

async def handle_edit_profile_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    choice = update.message.text
    if choice == "⬅️ Назад":
        return await show_my_profile(update, context)
    if choice == "🗑️ Удалить анкету":
        await update.message.reply_text(
            "Удалить анкету безвозвратно? Ты уверен(а)?",
            reply_markup=ReplyKeyboardMarkup([["✅ Да, удалить"], ["❌ Отмена"]], resize_keyboard=True)
        )
        return States.DELETE_CONFIRM.value
    if choice == "🖼️ Изменить фото":
        context.user_data['editing_photo'] = True
        context.user_data.setdefault('photo_ids', [])  # Инициализируем пустой список для новых фото
        await update.message.reply_text(
            "Отправь новое фото или нажми «❌ Удалить фото». 📷",
            reply_markup=ReplyKeyboardMarkup([["❌ Удалить фото"], ["⬅️ Назад"]], resize_keyboard=True)
        )
        return States.EDIT_PHOTO.value

    field_map = {
        "👤 Никнейм": "nickname",
        "📊 Winrate": "winrate",
        "⚔️ Линия": "line",
        "🏆 Ранг": "rank",
        "🎯 Цель": "goal",
        "📝 О себе": "about",
    }
    field = field_map.get(choice)
    if not field:
        await update.message.reply_text(
            "Выбери действие кнопкой!",
            reply_markup=ReplyKeyboardMarkup([
                ["👤 Никнейм", "📊 Winrate"],
                ["⚔️ Линия", "🏆 Ранг"],
                ["🎯 Цель", "📝 О себе"],
                ["🖼️ Изменить фото", "🗑️ Удалить анкету"],
                ["⬅️ Назад"]
            ], resize_keyboard=True)
        )
        return States.EDIT_PROFILE_CHOICE.value

    context.user_data['edit_field'] = field
    if field == "nickname":
        await update.message.reply_text(
            "Введи новый никнейм:",
            reply_markup=ReplyKeyboardMarkup([["⬅️ Назад"]], resize_keyboard=True)
        )
        return States.EDIT_PROFILE_INPUT.value
    if field == "winrate":
        await update.message.reply_text(
            "Введи новый winrate (0–100). Только цифры, без точек.\n\n💡 Если у тебя 50.6% — поставь 51",
            reply_markup=ReplyKeyboardMarkup([["⬅️ Назад"]], resize_keyboard=True)
        )
        return States.EDIT_PROFILE_INPUT.value
    if field == "line":
        context.user_data['selected_lines'] = set()
        await line_selection_menu(update, context)
        return States.GET_LINE.value
    if field == "rank":
        await go_to_rank_step(update, context)
        return States.GET_RANK.value
    if field == "goal":
        keyboard = [GOALS[:2], [GOALS[2]], ["⬅️ Назад"]]
        await update.message.reply_text(
            "Выбери новую цель:",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        )
        return States.GET_GOAL.value
    if field == "about":
        await update.message.reply_text(
            "Напиши обновлённое описание:",
            reply_markup=ReplyKeyboardMarkup([["⬅️ Назад"]], resize_keyboard=True)
        )
        return States.EDIT_PROFILE_INPUT.value

    return States.EDIT_PROFILE_CHOICE.value

async def process_edit_profile_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    choice = update.message.text
    if choice == "⬅️ Назад":
        return await show_my_profile(update, context)

    if 'edit_field' not in context.user_data:
        await update.message.reply_text(
            "Ой, что-то пошло не так! 😓 Начни редактирование заново.",
            reply_markup=ReplyKeyboardMarkup([["⬅️ Назад"]], resize_keyboard=True)
        )
        return await show_my_profile(update, context)

    field = context.user_data['edit_field']
    user_id = update.effective_user.id
    current = db.get_user_by_id(user_id)
    if not current:
        await update.message.reply_text(
            "Профиль не найден! Нажми /start.",
            reply_markup=ReplyKeyboardMarkup([["/start"]], resize_keyboard=True)
        )
        return States.SELECTING_ACTION.value

    new_data = current.to_dict()
    if field == "nickname":
        if not _valid_nickname(choice.strip()):
            await update.message.reply_text(
                "Ник некорректен! Попробуй снова.",
                reply_markup=ReplyKeyboardMarkup([["⬅️ Назад"]], resize_keyboard=True)
            )
            return States.EDIT_PROFILE_INPUT.value
        new_data["nickname"] = choice.strip()

    elif field == "winrate":
        winrate = _parse_winrate(choice)
        if winrate is None:
            await update.message.reply_text(
                "Введите целое число от 0 до 100. Только цифры, без точек и символов.\n\n💡 Например, 50.6% округлите до 51.",
                reply_markup=ReplyKeyboardMarkup([["⬅️ Назад"]], resize_keyboard=True)
            )
            return States.EDIT_PROFILE_INPUT.value
        new_data["winrate"] = winrate

    elif field == "line":
        # Значение уже выбрано в меню линий и сохранено ранее
        sel = context.user_data.get('selected_lines', set())
        if not sel:
            await update.message.reply_text(
                "Выбери линии кнопками!",
                reply_markup=ReplyKeyboardMarkup([["⬅️ Назад"]], resize_keyboard=True)
            )
            return States.GET_LINE.value
        new_data["line"] = "Везде" if "Везде" in sel else ", ".join(sorted(sel))

    elif field == "rank":
        # Значение заполняется в get_rank / get_mythic_rank
        prof = context.user_data.get('profile_data', {})
        # На случай если редактировали прямо
        rank = prof.get('rank') or new_data.get('rank')
        myth = prof.get('mythic_rank') if rank == "Мифический" else None
        new_data["rank"] = rank
        new_data["mythic_rank"] = myth

    elif field == "goal":
        if choice not in GOALS:
            await update.message.reply_text(
                "Выбери цель кнопкой!",
                reply_markup=ReplyKeyboardMarkup([GOALS[:2], [GOALS[2]], ["⬅️ Назад"]], resize_keyboard=True)
            )
            return States.GET_GOAL.value
        new_data["goal"] = choice

    elif field == "about":
        if len(choice) > 500:
            await update.message.reply_text(
                "До 500 символов, пожалуйста!",
                reply_markup=ReplyKeyboardMarkup([["⬅️ Назад"]], resize_keyboard=True)
            )
            return States.EDIT_PROFILE_INPUT.value
        new_data["about"] = choice

    new_data["last_active_timestamp"] = int(time.time())
    db.create_user_profile(new_data)
    await update.message.reply_text(
        "Готово! Обновил анкету. ✅",
        reply_markup=ReplyKeyboardMarkup([["⬅️ Назад"]], resize_keyboard=True)
    )
    return await show_my_profile(update, context)

async def handle_edit_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    # если пользователь отправил фото — обновим
    if update.message and update.message.photo:
        # Инициализируем список фотографий, если его еще нет
        context.user_data.setdefault('photo_ids', [])
        
        # Проверяем, достигли ли максимального количества фотографий
        if len(context.user_data['photo_ids']) >= MAX_PHOTOS:
            await update.message.reply_text(
                f"Вы уже добавили максимальное количество фотографий ({MAX_PHOTOS}). 📸",
                reply_markup=ReplyKeyboardMarkup([["➡️ Сохранить", "❌ Отмена"], ["⬅️ Назад"]], resize_keyboard=True)
            )
            return States.EDIT_PHOTO.value
        
        # Добавляем ID фотографии в список
        photo_id = update.message.photo[-1].file_id
        context.user_data['photo_ids'].append(photo_id)
        
        await update.message.reply_text(
            f"Фото добавлено! 📸 Ещё можешь добавить {MAX_PHOTOS - len(context.user_data['photo_ids'])} фото или сохранить изменения.",
            reply_markup=ReplyKeyboardMarkup([["📷 Добавить еще фото", "➡️ Сохранить"], ["❌ Отмена"], ["⬅️ Назад"]], resize_keyboard=True)
        )
        return States.EDIT_PHOTO.value

    # текстовые кнопки
    text = update.message.text if update.message else ""
    if text == "⬅️ Назад":
        return await show_my_profile(update, context)
    
    if text == "❌ Отмена":
        return await show_my_profile(update, context)
    
    if text == "❌ Удалить фото":
        # Проверяем, есть ли фото для удаления
        photo_ids = context.user_data.get('photo_ids', [])
        if not photo_ids:
            await update.message.reply_text(
                "У тебя нет загруженных фото! Нечего удалять 😜",
                reply_markup=ReplyKeyboardMarkup([["⬅️ Назад"]], resize_keyboard=True)
            )
            return States.EDIT_PHOTO.value
        
        # Создаем клавиатуру с кнопками для каждого фото
        keyboard = []
        row = []
        for i in range(1, MAX_PHOTOS + 1):
            if i <= len(photo_ids):
                row.append(f"{i}✅")
            else:
                row.append(f"{i}❌")
            if len(row) == 3:  # 3 кнопки в ряд
                keyboard.append(row)
                row = []
        if row:  # Добавляем оставшиеся кнопки
            keyboard.append(row)
        keyboard.append(["⬅️ Назад"])
        
        await update.message.reply_text(
            "Выбери фото для удаления:",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        )
        return States.DELETE_PHOTO.value
    
    if text == "➡️ Сохранить":
        # Проверяем, есть ли фото для сохранения
        photo_ids = context.user_data.get('photo_ids', [])
        if not photo_ids:
            # Если фото нет, спрашиваем подтверждение
            await update.message.reply_text(
                "Вы не добавили ни одного фото. Все текущие фото будут удалены. Продолжить?",
                reply_markup=ReplyKeyboardMarkup([["✅ Да, удалить фото", "❌ Отмена"]], resize_keyboard=True)
            )
            return States.EDIT_PHOTO.value
        
        # Сохраняем новые фото
        user_id = update.effective_user.id
        current = db.get_user_by_id(user_id)
        if current:
            new_data = current.to_dict()
            new_data["photo_ids"] = photo_ids
            new_data["last_active_timestamp"] = int(time.time())
            db.create_user_profile(new_data)
            await update.message.reply_text(
                "Фото обновлены! ✅",
                reply_markup=ReplyKeyboardMarkup([["⬅️ Назад"]], resize_keyboard=True)
            )
        return await show_my_profile(update, context)
    
    if text == "✅ Да, удалить фото":
        # Подтверждение удаления всех фото
        user_id = update.effective_user.id
        current = db.get_user_by_id(user_id)
        if current:
            new_data = current.to_dict()
            new_data["photo_ids"] = []
            new_data["last_active_timestamp"] = int(time.time())
            db.create_user_profile(new_data)
            await update.message.reply_text(
                "Фото удалены! 🗑️",
                reply_markup=ReplyKeyboardMarkup([["⬅️ Назад"]], resize_keyboard=True)
            )
        return await show_my_profile(update, context)
    
    if text == "📷 Добавить еще фото":
        await update.message.reply_text(
            "Отправь фото. 📷",
            reply_markup=ReplyKeyboardMarkup([["➡️ Сохранить", "❌ Отмена"], ["⬅️ Назад"]], resize_keyboard=True)
        )
        return States.EDIT_PHOTO.value

    # иначе повторим приглашение
    await update.message.reply_text(
        "Отправь фото или нажми «➡️ Сохранить». 📷",
        reply_markup=ReplyKeyboardMarkup([["➡️ Сохранить", "❌ Отмена"], ["⬅️ Назад"]], resize_keyboard=True)
    )
    return States.EDIT_PHOTO.value

async def handle_delete_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text
    
    if text == "⬅️ Назад":
        await update.message.reply_text(
            "Верну тебя назад, чтобы продолжили настраивать анкету 👌",
            reply_markup=ReplyKeyboardMarkup([["❌ Удалить фото", "⬅️ Назад"]], resize_keyboard=True)
        )
        return States.EDIT_PHOTO.value
    
    # Проверяем, что пользователь нажал на кнопку с номером фото
    if text.endswith("✅"):
        try:
            photo_num = int(text[:-1])  # Убираем ✅ и получаем номер
            photo_ids = context.user_data.get('photo_ids', [])
            
            if 1 <= photo_num <= len(photo_ids):
                # Удаляем фото
                removed_photo = photo_ids.pop(photo_num - 1)
                await update.message.reply_text(
                    f"Хей, фоточка №{photo_num} удалена 🗑️ Не переживай, всегда можно загрузить новую!",
                    reply_markup=ReplyKeyboardMarkup([["⬅️ Назад"]], resize_keyboard=True)
                )
                
                # Обновляем клавиатуру
                keyboard = []
                row = []
                for i in range(1, MAX_PHOTOS + 1):
                    if i <= len(photo_ids):
                        row.append(f"{i}✅")
                    else:
                        row.append(f"{i}❌")
                    if len(row) == 3:  # 3 кнопки в ряд
                        keyboard.append(row)
                        row = []
                if row:  # Добавляем оставшиеся кнопки
                    keyboard.append(row)
                keyboard.append(["⬅️ Назад"])
                
                await update.message.reply_text(
                    "Выбери фото для удаления:",
                    reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
                )
                return States.DELETE_PHOTO.value
            else:
                await update.message.reply_text(
                    "Такого фото нет! 😜",
                    reply_markup=ReplyKeyboardMarkup([["⬅️ Назад"]], resize_keyboard=True)
                )
                return States.DELETE_PHOTO.value
        except ValueError:
            await update.message.reply_text(
                "Что-то пошло не так! 😓 Попробуй ещё раз.",
                reply_markup=ReplyKeyboardMarkup([["⬅️ Назад"]], resize_keyboard=True)
            )
            return States.DELETE_PHOTO.value
    elif text.endswith("❌"):
        photo_num = int(text[:-1])  # Убираем ❌ и получаем номер
        await update.message.reply_text(
            f"Это фото не загружено, нечего удалять 😉",
            reply_markup=ReplyKeyboardMarkup([["⬅️ Назад"]], resize_keyboard=True)
        )
        return States.DELETE_PHOTO.value
    
    # Если что-то пошло не так
    await update.message.reply_text(
        "Выбери фото для удаления или нажми «Назад»!",
        reply_markup=ReplyKeyboardMarkup([["⬅️ Назад"]], resize_keyboard=True)
    )
    return States.DELETE_PHOTO.value

async def handle_delete_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    choice = update.message.text
    if choice == "✅ Да, удалить":
        user_id = update.effective_user.id
        db.delete_user(user_id)
        await update.message.reply_text(
            "Анкета удалена. Если захочешь вернуться — напиши /start",
            reply_markup=ReplyKeyboardMarkup([["/start"]], resize_keyboard=True)
        )
        return ConversationHandler.END
    if choice == "❌ Отмена":
        await show_my_profile(update, context)
        return States.MY_PROFILE.value
    await update.message.reply_text(
        "Пожалуйста, выбери вариант кнопкой!",
        reply_markup=ReplyKeyboardMarkup([["✅ Да, удалить"], ["❌ Отмена"]], resize_keyboard=True)
    )
    return States.DELETE_CONFIRM.value

def main():
    app = build_application()
    app.run_polling()

if __name__ == "__main__":
    main()

# ================== IMPORTS ==================
import asyncio, random, time, re, os, json, logging
from typing import Dict, Set, Optional, Tuple, Callable, List
from telegram import Update, BotCommand
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackContext, MessageHandler, filters
from telegram.error import TelegramError
from dotenv import load_dotenv
import nest_asyncio
from datetime import datetime

# ================== LOGGING ==================
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ================== ENV ==================
load_dotenv()
BOT_TOKEN = os.getenv("8123657321:AAFn-Kys2iGiklOr-pQp8_Lj3hVxolFGenE")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не знайдено в змінних середовища")

# ================== FILE PATHS ==================
BALANCES_FILE = "balances.json"
RANKS_FILE = "ranks.json"
CHANCES_FILE = "chances.json"
SHKONKA_FILE = "shkonka.json"
MOBILIZED_FILE = "mobilized.json"
POVISTKY_FILE = "povistky.json"
TRANSACTIONS_FILE = "transactions.json"

# ================== DATA STRUCTURES ==================
user_balance: Dict[int, int] = {}
user_chance: Dict[int, int] = {}
user_rank: Dict[int, int] = {}
shkonka_users: Dict[int, float] = {}
mobilizovani: Set[int] = set()
prizyvnyky: Set[int] = set()
transactions: Dict[int, List[Dict]] = {}  # Історія транзакцій

# ================== CONSTANTS ==================
RANKS = [
    "Ухилянт",  # 0
    "Рядовий ТЦК",  # 1
    "Сержант ТЦК",  # 2
    "Капітан ТЦК",  # 3
    "Майор ТЦК",  # 4
    "Полковник ТЦК",  # 5
    "Генерал ТЦК",  # 6
    "Головнокомандувач ТЦК"  # 7
]

# Шанс казино залежно від звання
RANK_CHANCES = {
    0: 5,  # Ухилянт
    1: 15,  # Рядовий ТЦК
    2: 20,  # Сержант ТЦК
    3: 25,  # Капітан ТЦК
    4: 30,  # Майор ТЦК
    5: 40,  # Полковник ТЦК
    6: 50,  # Генерал ТЦК
    7: 100  # Головнокомандувач ТЦК
}

# Головнокомандувачі за замовчуванням (додайте свої ID)
HEAD_COMMANDERS = {
    123456789,  # @x3_kto_lox (замініть на реальний ID)
    987654321  # @x3_kto (замініть на реальний ID)
}

RANK_PERMISSIONS = {
    7: ["ALL"],  # Головнокомандувач
    6: ["PROMOTE", "DEMOTE", "MOBILIZE", "DEMOBILIZE", "POVISTKA", "SHKONKA"],  # Генерал
    5: ["MOBILIZE", "DEMOBILIZE", "POVISTKA", "SHKONKA"],  # Полковник
    4: ["POVISTKA", "SHKONKA"],  # Майор
    3: ["SHKONKA"],  # Капітан
    2: ["SHKONKA"],  # Сержант
    1: [],  # Рядовий
    0: []  # Ухилянт
}

# Словник перекладу часу для українських команд
TIME_TRANSLATION = {
    # Український -> Англійський
    "хв": "m",
    "г": "h",
    "год": "h",
    "годин": "h",
    "д": "d",
    "дн": "d",
    "днів": "d",
    "т": "w",
    "тиж": "w",
    "тижд": "w",
    "тижнів": "w",
    "міс": "mos",
    "місяць": "mos",
    "місяців": "mos",
    "р": "r",
    "рік": "r",
    "років": "r",

    # Англійський залишається як є
    "m": "m",
    "h": "h",
    "d": "d",
    "w": "w",
    "mos": "mos",
    "r": "r"
}

TIME_MULTIPLIERS = {
    "m": 60,  # хвилини
    "h": 3600,  # години
    "d": 86400,  # дні
    "w": 604800,  # тижні
    "mos": 2592000,  # місяці (~30 днів)
    "r": 31536000  # рік
}

# ================== COMMAND MAPPING ==================
# Українські команди -> англійські функції
COMMAND_MAP = {
    # Статус та допомога
    "статус": "status",
    "стат": "status",
    "с": "status",
    "допомога": "help",
    "доп": "help",
    "д": "help",

    # Казино
    "казино": "casino",
    "каз": "casino",
    "к": "casino",

    # Шконка
    "шконка": "shkonka",
    "шк": "shkonka",
    "ш": "shkonka",
    "розшконка": "unshkonka",
    "розш": "unshkonka",
    "рш": "unshkonka",

    # Мобілізація
    "мобілізувати": "mobilize",
    "моб": "mobilize",
    "м": "mobilize",
    "демобілізувати": "demobilize",
    "демоб": "demobilize",
    "дем": "demobilize",
    "списокмоб": "list_mobilized",
    "спм": "list_mobilized",
    "см": "list_mobilized",

    # Повістки
    "повістка": "povistka",
    "пов": "povistka",
    "пв": "povistka",

    # Звання
    "підвищити": "promote",
    "під": "promote",
    "пвш": "promote",
    "понизити": "demote",
    "пон": "demote",
    "пн": "demote",

    # Адмін команди (тільки ГК)
    "додатигроші": "add_money",
    "додгр": "add_money",
    "дг": "add_money",
    "шанс": "set_chance",
    "шнс": "set_chance",
    "шс": "set_chance",
    "забратигроші": "remove_money",
    "забгр": "remove_money",
    "зг": "remove_money",
    "статистика": "admin_stats",
    "статс": "admin_stats",
    "стс": "admin_stats",
    "транзакції": "transactions_history",
    "трн": "transactions_history",
    "тр": "transactions_history",
}


# ================== DECORATORS FOR PERMISSION CHECKING ==================
def require_permission(permission: str = None, require_reply: bool = False, require_args: int = 0):
    """Декоратор для перевірки прав доступу"""

    def decorator(func):
        async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
            try:
                user_id = update.message.from_user.id

                # Автоматично робимо головнокомандувачів за ID
                if user_id in HEAD_COMMANDERS and user_id not in user_rank:
                    user_rank[user_id] = 7
                    user_balance[user_id] = 100000
                    user_chance[user_id] = 100
                    save_all_data()

                # Перевірка чи це reply повідомлення
                if require_reply and not update.message.reply_to_message:
                    await update.message.reply_text("❌ Ця команда потребує reply на повідомлення!")
                    return

                # Перевірка кількості аргументів
                if require_args > 0 and (not context.args or len(context.args) < require_args):
                    await update.message.reply_text(f"❌ Потрібно {require_args} аргумент(ів)!")
                    return

                user_rank_idx = user_rank.get(user_id, 1)

                # Якщо немає спеціальних прав - пропускаємо перевірку
                if permission is None:
                    return await func(update, context, *args, **kwargs)

                # Головнокомандувач має всі права
                if user_rank_idx == 7:
                    return await func(update, context, *args, **kwargs)

                # Перевірка конкретних прав
                user_permissions = RANK_PERMISSIONS.get(user_rank_idx, [])
                if permission in user_permissions or "ALL" in user_permissions:
                    return await func(update, context, *args, **kwargs)
                else:
                    await update.message.reply_text("❌ У вас недостатньо прав для цієї команди!")
                    return

            except Exception as e:
                logger.error(f"Error in {func.__name__}: {e}")
                await update.message.reply_text("❌ Сталася помилка при виконанні команди!")

        return wrapper

    return decorator


# ================== SAVE / LOAD ==================
def save_to_file(data: dict, filename: str) -> None:
    """Збереження даних у файл"""
    try:
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.debug(f"Дані збережено у {filename}")
    except Exception as e:
        logger.error(f"Помилка збереження у {filename}: {e}")


def load_from_file(filename: str) -> dict:
    """Завантаження даних з файлу"""
    if not os.path.exists(filename):
        logger.info(f"Файл {filename} не знайдено, створюємо новий")
        return {}

    try:
        with open(filename, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Конвертація ключів до int
        converted = {}
        for k, v in data.items():
            try:
                converted[int(k)] = v
            except (ValueError, TypeError):
                converted[k] = v

        logger.debug(f"Дані завантажено з {filename}")
        return converted
    except Exception as e:
        logger.error(f"Помилка завантаження з {filename}: {e}")
        return {}


def save_shkonka_data() -> None:
    """Збереження даних шконки"""
    try:
        # Конвертуємо timestamp у строки для JSON
        shkonka_to_save = {str(k): float(v) for k, v in shkonka_users.items()}
        save_to_file(shkonka_to_save, SHKONKA_FILE)
        logger.debug("Дані шконки збережено")
    except Exception as e:
        logger.error(f"Помилка збереження шконки: {e}")


def save_mobilized_data() -> None:
    """Збереження списку мобілізованих"""
    try:
        mobilized_list = list(mobilizovani)
        save_to_file({"mobilized": mobilized_list}, MOBILIZED_FILE)
        logger.debug("Список мобілізованих збережено")
    except Exception as e:
        logger.error(f"Помилка збереження мобілізованих: {e}")


def save_povistky_data() -> None:
    """Збереження списку з повістками"""
    try:
        povistky_list = list(prizyvnyky)
        save_to_file({"povistky": povistky_list}, POVISTKY_FILE)
        logger.debug("Список з повістками збережено")
    except Exception as e:
        logger.error(f"Помилка збереження повісток: {e}")


def save_all_data() -> None:
    """Збереження всіх даних у файли"""
    save_to_file(user_balance, BALANCES_FILE)
    save_to_file(user_rank, RANKS_FILE)
    save_to_file(user_chance, CHANCES_FILE)
    save_shkonka_data()
    save_mobilized_data()
    save_povistky_data()
    save_to_file(transactions, TRANSACTIONS_FILE)
    logger.info("Всі дані збережено")


def load_shkonka_data() -> Dict[int, float]:
    """Завантаження даних шконки"""
    data = load_from_file(SHKONKA_FILE)
    shkonka = {}

    for k, v in data.items():
        try:
            user_id = int(k)
            # Перевіряємо чи timestamp ще не минув
            if float(v) > time.time():
                shkonka[user_id] = float(v)
        except (ValueError, TypeError) as e:
            logger.warning(f"Помилка конвертації даних шконки для {k}: {e}")

    return shkonka


def load_mobilized_data() -> Set[int]:
    """Завантаження списку мобілізованих"""
    data = load_from_file(MOBILIZED_FILE)

    if isinstance(data, dict) and "mobilized" in data:
        # Новий формат
        mobilized_list = data["mobilized"]
    elif isinstance(data, list):
        # Старий формат
        mobilized_list = data
    else:
        # Пустий файл або інший формат
        mobilized_list = []

    # Конвертуємо всі елементи до int
    mobilized_set = set()
    for item in mobilized_list:
        try:
            mobilized_set.add(int(item))
        except (ValueError, TypeError):
            logger.warning(f"Помилка конвертації ID мобілізованого: {item}")

    return mobilized_set


def load_povistky_data() -> Set[int]:
    """Завантаження списку з повістками"""
    data = load_from_file(POVISTKY_FILE)

    if isinstance(data, dict) and "povistky" in data:
        # Новий формат
        povistky_list = data["povistky"]
    elif isinstance(data, list):
        # Старий формат
        povistky_list = data
    else:
        # Пустий файл або інший формат
        povistky_list = []

    # Конвертуємо всі елементи до int
    povistky_set = set()
    for item in povistky_list:
        try:
            povistky_set.add(int(item))
        except (ValueError, TypeError):
            logger.warning(f"Помилка конвертації ID з повісткою: {item}")

    return povistky_set


def load_all_data() -> None:
    """Завантаження всіх даних з файлів"""
    global user_balance, user_chance, user_rank, shkonka_users, mobilizovani, prizyvnyky, transactions

    # Завантажуємо дані з окремих файлів
    user_balance = load_from_file(BALANCES_FILE)
    user_rank = load_from_file(RANKS_FILE)
    user_chance = load_from_file(CHANCES_FILE)

    # Завантажуємо шконку
    shkonka_users = load_shkonka_data()

    # Завантажуємо множини
    mobilizovani = load_mobilized_data()
    prizyvnyky = load_povistky_data()

    # Завантажуємо транзакції
    transactions = load_from_file(TRANSACTIONS_FILE)

    # Перевіряємо чи головнокомандувачі все ще мають права
    for hc_id in HEAD_COMMANDERS:
        if hc_id not in user_rank or user_rank[hc_id] != 7:
            user_rank[hc_id] = 7
            if hc_id not in user_balance:
                user_balance[hc_id] = 100000
            if hc_id not in user_chance:
                user_chance[hc_id] = 100

    logger.info("Всі дані завантажено")
    logger.info(f"Завантажено {len(mobilizovani)} мобілізованих")
    logger.info(f"Завантажено {len(shkonka_users)} користувачів у шконці")
    logger.info(f"Завантажено {len(prizyvnyky)} користувачів з повістками")


def add_transaction(user_id: int, amount: int, transaction_type: str, reason: str = "",
                    executor_id: int = None) -> None:
    """Додати транзакцію в історію"""
    if user_id not in transactions:
        transactions[user_id] = []

    transaction = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "amount": amount,
        "type": transaction_type,  # "add", "remove", "casino_win", "casino_lose"
        "reason": reason,
        "executor": executor_id,
        "balance_after": user_balance.get(user_id, 0)
    }

    transactions[user_id].append(transaction)

    # Зберігаємо лише останні 50 транзакцій
    if len(transactions[user_id]) > 50:
        transactions[user_id] = transactions[user_id][-50:]

    save_to_file(transactions, TRANSACTIONS_FILE)


# ================== HELPERS ==================
def init_user(user_id: int) -> None:
    """Ініціалізація нового користувача"""
    if user_id not in user_balance:
        user_balance[user_id] = 1000
        save_to_file(user_balance, BALANCES_FILE)
    if user_id not in user_rank:
        user_rank[user_id] = 1  # Початкове звання - Рядовий
        save_to_file(user_rank, RANKS_FILE)
    # Встановлюємо шанс залежно від звання
    if user_id not in user_chance:
        rank_idx = user_rank.get(user_id, 1)
        user_chance[user_id] = RANK_CHANCES.get(rank_idx, 15)
        save_to_file(user_chance, CHANCES_FILE)


def get_rank_index(user_id: int) -> int:
    """Отримати індекс звання користувача"""
    return user_rank.get(user_id, 1)


def get_rank_name(user_id: int) -> str:
    """Отримати назву звання користувача"""
    rank_idx = get_rank_index(user_id)
    return RANKS[min(max(rank_idx, 0), len(RANKS) - 1)]


def is_head_commander(user_id: int) -> bool:
    """Перевірити чи є користувач Головнокомандувачем"""
    return get_rank_index(user_id) == 7


def get_status_for_user(user_id: int) -> str:
    """Отримати статус користувача у текстовому вигляді"""
    init_user(user_id)

    in_shkonka = user_id in shkonka_users
    shkonka_info = ""
    if in_shkonka:
        remaining = shkonka_users[user_id] - time.time()
        shkonka_info = f"\n⛓ У шконці: {format_time(int(remaining))}"

    is_mobilized = user_id in mobilizovani
    # Якщо є звання (не ухилянт) - показуємо ТЦК, інакше цивільний
    rank_idx = get_rank_index(user_id)
    if rank_idx > 0:  # Якщо не ухилянт
        mobilized_info = "🪖 Мобілізований" if is_mobilized else "🏠 ТЦК"
    else:
        mobilized_info = "🪖 Мобілізований" if is_mobilized else "🏠 Цивільний"

    has_povistka = user_id in prizyvnyky
    povistka_info = "\n📄 Має повістку" if has_povistka else ""

    # Перевіряємо чи користувач головнокомандувач
    hc_info = "👑 ГОЛОВНОКОМАНДУВАЧ\n" if is_head_commander(user_id) else ""

    # Баланс з форматуванням
    balance_formatted = f"{user_balance[user_id]:,}".replace(",", " ")

    # Останні транзакції
    last_transactions = ""
    if user_id in transactions and transactions[user_id]:
        last_tx = transactions[user_id][-1]  # Остання транзакція
        tx_type_emoji = {
            "add": "➕",
            "remove": "➖",
            "casino_win": "🎰➕",
            "casino_lose": "🎰➖"
        }
        emoji = tx_type_emoji.get(last_tx["type"], "💸")
        last_transactions = f"\n{emoji} Остання операція: {last_tx['timestamp']}"
        if last_tx["reason"]:
            last_transactions += f"\n📝 Причина: {last_tx['reason']}"

    return (
        f"{hc_info}"
        f"👤 ID: {user_id}\n"
        f"💰 Баланс: {balance_formatted}\n"
        f"🎯 Шанс у казино: {user_chance[user_id]}%\n"
        f"🎖 Звання: {get_rank_name(user_id)}\n"
        f"{mobilized_info}{povistka_info}"
        f"{shkonka_info}"
        f"{last_transactions}"
    )


def parse_duration_uk(duration_str: str) -> Optional[int]:
    """Парсинг українського рядка тривалості у секунди"""
    # Видаляємо пробіли та переводимо в нижній регістр
    duration_str = duration_str.lower().strip()

    # Шукаємо число та одиницю часу
    match = re.match(r"(\d+)\s*([а-яa-z]+)", duration_str)
    if not match:
        return None

    amount = int(match.group(1))
    unit = match.group(2)

    # Перевіряємо чи є така одиниця часу
    if unit in TIME_TRANSLATION:
        english_unit = TIME_TRANSLATION[unit]
        if english_unit in TIME_MULTIPLIERS:
            return amount * TIME_MULTIPLIERS[english_unit]

    return None


def parse_duration(duration_str: str) -> Optional[int]:
    """Універсальний парсинг часу (англійський та український)"""
    # Спочатку пробуємо український формат
    result = parse_duration_uk(duration_str)
    if result:
        return result

    # Потім англійський формат
    match = re.fullmatch(r"(\d+)(m|h|d|w|mos|r)", duration_str.lower())
    if not match:
        return None

    amount = int(match.group(1))
    unit = match.group(2)

    if unit in TIME_MULTIPLIERS:
        return amount * TIME_MULTIPLIERS[unit]

    return None


def format_time(seconds: int) -> str:
    """Форматування часу у читабельний вигляд"""
    if seconds < 60:
        return f"{seconds}с"
    elif seconds < 3600:
        return f"{seconds // 60}хв"
    elif seconds < 86400:
        return f"{seconds // 3600}г"
    elif seconds < 604800:
        return f"{seconds // 86400}д"
    elif seconds < 2592000:
        return f"{seconds // 604800}т"
    else:
        return f"{seconds // 2592000}міс"


# ================== SHKONKA ==================
async def shkonka_job(context: CallbackContext) -> None:
    """Перевірка закінчення часу в шконці"""
    now = time.time()
    ended = [user_id for user_id, end_time in shkonka_users.items() if end_time <= now]

    for user_id in ended:
        shkonka_users.pop(user_id, None)
        try:
            await context.bot.send_message(
                user_id,
                "🔓 Ваш час у шконці закінчився! Ви вільні."
            )
        except TelegramError as e:
            logger.error(f"Не вдалося відправити повідомлення {user_id}: {e}")

    if ended:
        save_shkonka_data()


# ================== USER COMMANDS ==================
@require_permission()
async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Перегляд статусу користувача (свого або через reply)"""
    # Якщо це reply - показуємо статус того, на кого reply
    if update.message.reply_to_message:
        target_id = update.message.reply_to_message.from_user.id
        status_text = get_status_for_user(target_id)
        # Додаємо примітку, що це статус іншого користувача
        status_text = f"📋 Статус користувача {target_id}:\n\n{status_text}"
    else:
        # Якщо не reply - показуємо свій статус
        user_id = update.message.from_user.id
        status_text = get_status_for_user(user_id)
        status_text = f"📋 Ваш статус:\n\n{status_text}"

    await update.message.reply_text(status_text)


@require_permission(permission="SHKONKA", require_reply=True, require_args=1)
async def cmd_shkonka(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Посадити користувача в шконку"""
    target_id = update.message.reply_to_message.from_user.id
    init_user(target_id)

    # Не можна садити в шконку вищих за себе
    executor_rank = get_rank_index(update.message.from_user.id)
    target_rank = get_rank_index(target_id)

    if target_rank > executor_rank and not is_head_commander(update.message.from_user.id):
        await update.message.reply_text("❌ Не можна садити в шконку вищого за званням!")
        return

    duration_seconds = parse_duration(context.args[0])
    if not duration_seconds:
        await update.message.reply_text(
            "❌ Невірний формат часу!\n"
            "🇺🇦 Український: 30хв, 2г, 1д, 1т, 1міс, 1р\n"
            "🇬🇧 Англійський: 30m, 2h, 1d, 1w, 1mos, 1r"
        )
        return

    end_time = time.time() + duration_seconds
    shkonka_users[target_id] = end_time

    save_shkonka_data()

    await update.message.reply_text(
        f"⛓ Користувача {target_id} посаджено в шконку на {format_time(duration_seconds)}"
    )


@require_permission(permission="SHKONKA", require_reply=True)
async def cmd_unshkonka(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Випустити користувача з шконки"""
    target_id = update.message.reply_to_message.from_user.id

    if target_id not in shkonka_users:
        await update.message.reply_text("❌ Цей користувач не в шконці!")
        return

    shkonka_users.pop(target_id, None)
    save_shkonka_data()

    await update.message.reply_text(f"🔓 Користувача {target_id} випущено з шконки")


@require_permission(permission="MOBILIZE", require_reply=True)
async def cmd_mobilize(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Мобілізувати користувача"""
    target_id = update.message.reply_to_message.from_user.id
    init_user(target_id)

    if target_id in mobilizovani:
        await update.message.reply_text("❌ Цей користувач вже мобілізований!")
        return

    mobilizovani.add(target_id)
    save_mobilized_data()

    await update.message.reply_text(f"🪖 Користувача {target_id} мобілізовано!")


@require_permission(permission="DEMOBILIZE", require_reply=True)
async def cmd_demobilize(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Демобілізувати користувача"""
    target_id = update.message.reply_to_message.from_user.id

    if target_id not in mobilizovani:
        await update.message.reply_text("❌ Цей користувач не мобілізований!")
        return

    mobilizovani.remove(target_id)
    save_mobilized_data()

    await update.message.reply_text(f"🏠 Користувача {target_id} демобілізовано!")


@require_permission()
async def cmd_list_mobilized(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Список мобілізованих"""
    if not mobilizovani:
        await update.message.reply_text("📭 Список мобілізованих порожній")
        return

    message = "🪖 Мобілізовані користувачі:\n"
    for idx, user_id in enumerate(mobilizovani, 1):
        rank_name = get_rank_name(user_id)
        is_hc = "👑 " if is_head_commander(user_id) else ""
        message += f"{idx}. {is_hc}{user_id} - {rank_name}\n"

    await update.message.reply_text(message[:4000])  # Обмеження Telegram


@require_permission(permission="POVISTKA", require_reply=True)
async def cmd_povistka(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Видати повістку"""
    target_id = update.message.reply_to_message.from_user.id
    init_user(target_id)

    if target_id in prizyvnyky:
        await update.message.reply_text("❌ Цей користувач вже має повістку!")
        return

    prizyvnyky.add(target_id)
    save_povistky_data()

    await update.message.reply_text(f"📄 Повістку видано користувачу {target_id}")


@require_permission(permission="PROMOTE", require_reply=True)
async def cmd_promote(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Підвищити звання"""
    target_id = update.message.reply_to_message.from_user.id
    init_user(target_id)

    current_rank = get_rank_index(target_id)
    if current_rank >= 7:
        await update.message.reply_text("❌ Неможливо підвищити - вже найвище звання!")
        return

    user_rank[target_id] = current_rank + 1
    # Оновлюємо шанс при підвищенні
    user_chance[target_id] = RANK_CHANCES.get(current_rank + 1, 15)

    save_to_file(user_rank, RANKS_FILE)
    save_to_file(user_chance, CHANCES_FILE)

    await update.message.reply_text(
        f"🎉 Користувача {target_id} підвищено!\n"
        f"🎖 Нове звання: {get_rank_name(target_id)}\n"
        f"🎯 Новий шанс у казино: {user_chance[target_id]}%"
    )


@require_permission(permission="DEMOTE", require_reply=True)
async def cmd_demote(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Понизити звання"""
    target_id = update.message.reply_to_message.from_user.id
    init_user(target_id)

    current_rank = get_rank_index(target_id)
    if current_rank <= 0:
        await update.message.reply_text("❌ Неможливо понизити - вже найнижче звання!")
        return

    user_rank[target_id] = current_rank - 1
    # Оновлюємо шанс при пониженні
    user_chance[target_id] = RANK_CHANCES.get(current_rank - 1, 15)

    save_to_file(user_rank, RANKS_FILE)
    save_to_file(user_chance, CHANCES_FILE)

    await update.message.reply_text(
        f"📉 Користувача {target_id} понижено!\n"
        f"🎖 Нове звання: {get_rank_name(target_id)}\n"
        f"🎯 Новий шанс у казино: {user_chance[target_id]}%"
    )


# ================== CASINO ==================
@require_permission()
async def cmd_casino(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Гра в казино"""
    user_id = update.message.from_user.id
    init_user(user_id)

    # Перевірка чи користувач в шконці
    if user_id in shkonka_users:
        await update.message.reply_text("❌ Не можна грати в казино з шконки!")
        return

    # Перевірка аргументів
    if not context.args:
        await update.message.reply_text(
            "🎰 КАЗИНО ТЦК\n"
            "Використання: /casino <ставка> або .каз <ставка>\n\n"
            f"💰 Ваш баланс: {user_balance[user_id]:,}\n"
            f"🎯 Ваш шанс: {user_chance[user_id]}%\n"
            f"🎖 Ваше звання: {get_rank_name(user_id)}\n\n"
            "📊 Шанси за званнями:\n"
            "• Ухилянт: 5%\n• Рядовий: 15%\n• Сержант: 20%\n"
            "• Капітан: 25%\n• Майор: 30%\n• Полковник: 40%\n"
            "• Генерал: 50%\n• Головнокомандувач: 100%"
        )
        return

    try:
        bet = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ Ставка повинна бути числом!")
        return

    if bet <= 0:
        await update.message.reply_text("❌ Ставка повинна бути більше 0!")
        return

    if bet > user_balance[user_id]:
        await update.message.reply_text(
            f"❌ Недостатньо коштів!\n"
            f"💰 Ваш баланс: {user_balance[user_id]:,}\n"
            f"💳 Потрібно: {bet:,}"
        )
        return

    # Розіграш
    roll = random.randint(1, 100)
    if roll <= user_chance[user_id]:
        win = bet * 2  # Виграш 2x ставки
        user_balance[user_id] += win
        result_text = f"🎉 ВИГРАШ! +{win:,}💰\n💰 Ваш баланс: {user_balance[user_id]:,}"
        emoji = "🎊"
        tx_type = "casino_win"
        tx_reason = f"Виграш у казино (ставка: {bet:,})"
    else:
        user_balance[user_id] -= bet
        result_text = f"💸 ПРОГРАШ! -{bet:,}💰\n💰 Ваш баланс: {user_balance[user_id]:,}"
        emoji = "😞"
        tx_type = "casino_lose"
        tx_reason = f"Програш у казино (ставка: {bet:,})"

    # Додаємо транзакцію
    add_transaction(user_id, bet if tx_type == "casino_lose" else win, tx_type, tx_reason)
    save_to_file(user_balance, BALANCES_FILE)

    await update.message.reply_text(
        f"{emoji} РЕЗУЛЬТАТ КАЗИНО:\n"
        f"🎰 Випало: {roll}/100 (потрібно ≤{user_chance[user_id]})\n"
        f"🎖 Ваше звання: {get_rank_name(user_id)}\n"
        f"🎯 Ваш шанс: {user_chance[user_id]}%\n\n"
        f"{result_text}"
    )


# ================== ADMIN COMMANDS (Головнокомандувач) ==================
@require_permission(permission="ALL", require_reply=True, require_args=1)
async def cmd_add_money(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Додати гроші (тільки Головнокомандувач)"""
    target_id = update.message.reply_to_message.from_user.id
    init_user(target_id)

    try:
        amount = int(context.args[0])

        # Отримуємо причину (якщо є)
        reason = " ".join(context.args[1:]) if len(context.args) > 1 else "Без причини"

        user_balance[target_id] += amount

        # Додаємо транзакцію
        executor_id = update.message.from_user.id
        add_transaction(target_id, amount, "add", reason, executor_id)

        save_to_file(user_balance, BALANCES_FILE)

        await update.message.reply_text(
            f"💰 Користувачу {target_id} додано {amount:,} грошей\n"
            f"💰 Новий баланс: {user_balance[target_id]:,}\n"
            f"📝 Причина: {reason}"
        )
    except ValueError:
        await update.message.reply_text(
            "❌ Невірний формат!\n"
            "Використання: .дг <сума> [причина]\n"
            "Приклад: .дг 5000 Виплата зарплати\n"
            "Приклад: .дг 10000 Премія за службу"
        )


@require_permission(permission="ALL", require_reply=True, require_args=1)
async def cmd_set_chance(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Встановити шанс (тільки Головнокомандувач)"""
    target_id = update.message.reply_to_message.from_user.id
    init_user(target_id)

    try:
        chance = int(context.args[0])
        if chance < 1 or chance > 100:
            await update.message.reply_text("❌ Шанс повинен бути від 1 до 100!")
            return

        user_chance[target_id] = chance
        save_to_file(user_chance, CHANCES_FILE)

        await update.message.reply_text(
            f"🎯 Користувачу {target_id} встановлено шанс {chance}%\n"
            f"⚠️ Увага: при зміні звання шанс може змінитись!"
        )
    except ValueError:
        await update.message.reply_text("❌ Шанс повинен бути числом!")


@require_permission(permission="ALL", require_reply=True, require_args=1)
async def cmd_remove_money(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Забрати гроші (тільки Головнокомандувач)"""
    target_id = update.message.reply_to_message.from_user.id
    init_user(target_id)

    try:
        amount = int(context.args[0])

        # Отримуємо причину (якщо є)
        reason = " ".join(context.args[1:]) if len(context.args) > 1 else "Без причини"

        user_balance[target_id] = max(0, user_balance[target_id] - amount)

        # Додаємо транзакцію
        executor_id = update.message.from_user.id
        add_transaction(target_id, amount, "remove", reason, executor_id)

        save_to_file(user_balance, BALANCES_FILE)

        await update.message.reply_text(
            f"💸 У користувача {target_id} забрано {amount:,} грошей\n"
            f"💰 Новий баланс: {user_balance[target_id]:,}\n"
            f"📝 Причина: {reason}"
        )
    except ValueError:
        await update.message.reply_text(
            "❌ Невірний формат!\n"
            "Використання: .зг <сума> [причина]\n"
            "Приклад: .зг 2000 Штраф за невиконання\n"
            "Приклад: .зг 5000 Оплата штрафу"
        )


@require_permission(permission="ALL")
async def cmd_admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Статистика для адміністратора"""
    total_users = len(set(list(user_balance.keys()) +
                          list(user_chance.keys()) +
                          list(user_rank.keys())))

    total_balance = sum(user_balance.values())
    total_mobilized = len(mobilizovani)
    total_in_shkonka = len(shkonka_users)
    total_with_povistka = len(prizyvnyky)

    rank_distribution = {}
    for rank_idx in user_rank.values():
        rank_name = RANKS[min(max(rank_idx, 0), len(RANKS) - 1)]
        rank_distribution[rank_name] = rank_distribution.get(rank_name, 0) + 1

    stats_text = (
        f"📊 СТАТИСТИКА СИСТЕМИ ТЦК\n\n"
        f"👥 Загалом користувачів: {total_users}\n"
        f"💰 Загальний баланс: {total_balance:,}\n"
        f"🪖 Мобілізованих: {total_mobilized}\n"
        f"⛓ У шконці: {total_in_shkonka}\n"
        f"📄 З повістками: {total_with_povistka}\n\n"
        f"🎖 РОЗПОДІЛ ЗВАНЬ:\n"
    )

    for rank_name, count in sorted(rank_distribution.items()):
        chance = RANK_CHANCES.get(RANKS.index(rank_name), 15)
        stats_text += f"  {rank_name}: {count} (шанс: {chance}%)\n"

    # Додаємо головнокомандувачів
    hc_list = [uid for uid in HEAD_COMMANDERS if uid in user_rank]
    if hc_list:
        stats_text += f"\n👑 Головнокомандувачі: {', '.join(map(str, hc_list))}"

    await update.message.reply_text(stats_text)


@require_permission(permission="ALL")
async def cmd_transactions_history(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Історія транзакцій користувача"""
    user_id = update.message.from_user.id

    # Якщо це reply - показуємо історію того, на кого reply
    if update.message.reply_to_message:
        target_id = update.message.reply_to_message.from_user.id
        if target_id not in transactions or not transactions[target_id]:
            await update.message.reply_text(f"📭 У користувача {target_id} немає транзакцій")
            return

        history_text = f"📋 Історія транзакцій користувача {target_id}:\n\n"
        tx_list = transactions[target_id][-10:]  # Останні 10 транзакцій

    else:
        # Якщо не reply - показуємо свою історію
        if user_id not in transactions or not transactions[user_id]:
            await update.message.reply_text("📭 У вас немає транзакцій")
            return

        history_text = "📋 Ваша історія транзакцій:\n\n"
        tx_list = transactions[user_id][-10:]  # Останні 10 транзакцій

    for i, tx in enumerate(reversed(tx_list), 1):
        tx_type_emoji = {
            "add": "➕",
            "remove": "➖",
            "casino_win": "🎰➕",
            "casino_lose": "🎰➖"
        }
        emoji = tx_type_emoji.get(tx["type"], "💸")

        amount_prefix = "+" if tx["type"] in ["add", "casino_win"] else "-"

        history_text += f"{i}. {emoji} {tx['timestamp']}\n"
        history_text += f"   {amount_prefix}{tx['amount']:,} → Баланс: {tx['balance_after']:,}\n"
        if tx["reason"]:
            history_text += f"   📝 {tx['reason']}\n"
        history_text += "\n"

    await update.message.reply_text(history_text)


# ================== HELP COMMAND ==================
@require_permission()
async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Допомога по командам"""
    user_id = update.message.from_user.id
    user_rank_idx = get_rank_index(user_id)

    help_text = "🎖 ДОВІДКА ПО КОМАНДАМ ТЦК БОТА\n\n"
    help_text += "🇺🇦 Українські команди (з крапкою та скорочення):\n"
    help_text += "🇬🇧 Англійські команди (з слешем):\n\n"

    # Загальні команди
    help_text += "👤 ЗАГАЛЬНІ КОМАНДИ:\n"
    help_text += ".статус / .с  або  /status - Статус (можна reply на іншого)\n"
    help_text += ".казино <ставка> / .к  або  /casino <ставка> - Гра в казино\n"
    help_text += ".допомога / .д  або  /help - Ця довідка\n\n"

    # Команди за званнями
    user_permissions = RANK_PERMISSIONS.get(user_rank_idx, [])

    if any(perm in user_permissions for perm in ["SHKONKA", "ALL"]):
        help_text += "⛓ КОМАНДИ ШКОНКИ (reply):\n"
        help_text += ".шконка <час> / .шк  або  /shkonka <час>\n"
        help_text += ".розшконка / .рш  або  /unshkonka\n"
        help_text += "Формат: 30хв, 2г, 1д, 1т, 1міс, 1р\n"
        help_text += "Або: 30m, 2h, 1d, 1w, 1mos, 1r\n\n"

    if any(perm in user_permissions for perm in ["MOBILIZE", "DEMOBILIZE", "ALL"]):
        help_text += "🪖 МОБІЛІЗАЦІЯ (reply):\n"
        help_text += ".мобілізувати / .моб  або  /mobilize\n"
        help_text += ".демобілізувати / .демоб  або  /demobilize\n"
        help_text += ".списокмоб / .см  або  /list_mobilized\n\n"

    if any(perm in user_permissions for perm in ["POVISTKA", "ALL"]):
        help_text += "📄 ПОВІСТКИ (reply):\n"
        help_text += ".повістка / .пов  або  /povistka\n\n"

    if any(perm in user_permissions for perm in ["PROMOTE", "DEMOTE", "ALL"]):
        help_text += "🎖 ЗВАННЯ (reply):\n"
        help_text += ".підвищити / .під  або  /promote\n"
        help_text += ".понизити / .пон  або  /demote\n\n"

    if is_head_commander(user_id):
        help_text += "👑 КОМАНДИ ГОЛОВНОКОМАНДУВАЧА:\n"
        help_text += ".додатигроші <сума> [причина] / .дг\n"
        help_text += "  Приклад: .дг 5000 Виплата зарплати\n"
        help_text += ".забратигроші <сума> [причина] / .зг\n"
        help_text += "  Приклад: .зг 2000 Штраф\n"
        help_text += ".шанс <1-100> / .шс\n"
        help_text += ".статистика / .стс  або  /admin_stats\n"
        help_text += ".транзакції / .тр  - Історія транзакцій (можна reply)\n\n"

    # Інформація про шанси
    help_text += "📊 ШАНСИ У КАЗИНО ЗА ЗВАННЯМ:\n"
    for i, rank in enumerate(RANKS):
        if i <= user_rank_idx or is_head_commander(user_id):
            help_text += f"  {rank}: {RANK_CHANCES.get(i, 15)}%\n"

    help_text += f"\n🎖 Ваше звання: {get_rank_name(user_id)}\n"
    help_text += f"🎯 Ваш шанс у казино: {user_chance.get(user_id, 15)}%\n"
    help_text += "📖 Скорочені команди працюють з крапкою (напр. .с, .к, .шк)"

    await update.message.reply_text(help_text)


# ================== START COMMAND ==================
@require_permission()
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Команда старт"""
    user_id = update.message.from_user.id
    init_user(user_id)

    # Перевіряємо чи користувач головнокомандувач
    if is_head_commander(user_id):
        welcome = "👑 ВІТАЄМО, ГОЛОВНОКОМАНДУВАЧ ТЦК!\n"
        welcome += "У вас повні права в системі ТЦК.\n\n"
        welcome += "💰 Ваш баланс: 100,000\n"
        welcome += "🎯 Ваш шанс у казино: 100%\n\n"
        welcome += "📁 Дані зберігаються у окремих файлах:\n"
        welcome += "• balances.json - баланси\n"
        welcome += "• ranks.json - звання\n"
        welcome += "• chances.json - шанси\n"
        welcome += "• shkonka.json - дані шконки\n"
        welcome += "• mobilized.json - мобілізовані\n"
        welcome += "• povistky.json - повістки\n"
        welcome += "• transactions.json - транзакції\n\n"
        welcome += "Використовуйте .допомога для списку команд"
    else:
        rank_name = get_rank_name(user_id)
        chance = user_chance[user_id]
        welcome = f"🎖 Вітаємо в системі ТЦК, {rank_name}!\n\n"
        welcome += f"💰 Ваш стартовий баланс: 1,000\n"
        welcome += f"🎯 Ваш шанс у казино: {chance}%\n"
        welcome += f"🏠 Ваш статус: ТЦК\n\n"
        welcome += "📈 Підвищуйте звання для збільшення шансу!\n"
        welcome += "Використовуйте .допомога для списку команд"

    await update.message.reply_text(welcome)


# ================== UKRAINIAN COMMAND HANDLER ==================
async def handle_ukrainian_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обробник українських команд з крапкою"""
    if not update.message.text:
        return

    text = update.message.text.strip()

    # Перевіряємо чи це українська команда (починається з крапки)
    if not text.startswith('.'):
        return

    # Видаляємо крапку і розбиваємо на команду та аргументи
    parts = text[1:].split(maxsplit=1)
    if not parts:
        return

    command = parts[0].lower()
    args = parts[1] if len(parts) > 1 else ""

    # Мапимо українську команду на англійську
    if command not in COMMAND_MAP:
        await update.message.reply_text(f"❌ Невідома команда: .{command}\nВикористовуйте .допомога")
        return

    english_command = COMMAND_MAP[command]

    # Створюємо імітацію контексту з аргументами
    if args:
        context.args = args.split()
    else:
        context.args = []

    # Викликаємо відповідну функцію
    command_handlers = {
        "status": cmd_status,
        "help": cmd_help,
        "casino": cmd_casino,
        "shkonka": cmd_shkonka,
        "unshkonka": cmd_unshkonka,
        "mobilize": cmd_mobilize,
        "demobilize": cmd_demobilize,
        "list_mobilized": cmd_list_mobilized,
        "povistka": cmd_povistka,
        "promote": cmd_promote,
        "demote": cmd_demote,
        "add_money": cmd_add_money,
        "set_chance": cmd_set_chance,
        "remove_money": cmd_remove_money,
        "admin_stats": cmd_admin_stats,
        "transactions_history": cmd_transactions_history,
    }

    if english_command in command_handlers:
        await command_handlers[english_command](update, context)


# ================== MAIN ==================
async def main() -> None:
    """Головна функція"""
    # Завантаження всіх даних
    load_all_data()

    # Створення додатку
    application = Application.builder().token(BOT_TOKEN).build()

    # Додавання job для перевірки шконки
    application.job_queue.run_repeating(shkonka_job, interval=10, first=10)

    # Реєстрація англійських команд (з слешем)
    commands = {
        "start": cmd_start,
        "status": cmd_status,
        "help": cmd_help,
        "shkonka": cmd_shkonka,
        "unshkonka": cmd_unshkonka,
        "mobilize": cmd_mobilize,
        "demobilize": cmd_demobilize,
        "list_mobilized": cmd_list_mobilized,
        "povistka": cmd_povistka,
        "promote": cmd_promote,
        "demote": cmd_demote,
        "casino": cmd_casino,
        "add_money": cmd_add_money,
        "set_chance": cmd_set_chance,
        "remove_money": cmd_remove_money,
        "admin_stats": cmd_admin_stats,
    }

    for command, handler in commands.items():
        application.add_handler(CommandHandler(command, handler))

    # Додаємо обробник українських команд (з крапкою)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_ukrainian_command))

    # Встановлення меню команд (англійські)
    bot_commands = [
        BotCommand("start", "Початок роботи"),
        BotCommand("status", "Перевірити статус (reply на іншого)"),
        BotCommand("help", "Довідка по командам"),
        BotCommand("casino", "Гра в казино"),
        BotCommand("shkonka", "Посадити в шконку (reply)"),
        BotCommand("mobilize", "Мобілізувати (reply)"),
        BotCommand("promote", "Підвищити звання (reply)"),
        BotCommand("admin_stats", "Статистика (ГК)")
    ]

    await application.bot.set_my_commands(bot_commands)

    logger.info("🤖 Бот запущено успішно!")
    logger.info(f"👑 Головнокомандувачі: {HEAD_COMMANDERS}")
    logger.info("📁 Файли даних:")
    logger.info(f"  • {BALANCES_FILE} - баланси")
    logger.info(f"  • {RANKS_FILE} - звання")
    logger.info(f"  • {CHANCES_FILE} - шанси")
    logger.info(f"  • {SHKONKA_FILE} - шконка ({len(shkonka_users)} користувачів)")
    logger.info(f"  • {MOBILIZED_FILE} - мобілізовані ({len(mobilizovani)} користувачів)")
    logger.info(f"  • {POVISTKY_FILE} - повістки ({len(prizyvnyky)} користувачів)")
    logger.info(f"  • {TRANSACTIONS_FILE} - транзакції")

    # Запуск
    await application.run_polling()


if __name__ == "__main__":
    nest_asyncio.apply()

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот зупинено користувачем")
    except Exception as e:

        logger.error(f"Критична помилка: {e}")

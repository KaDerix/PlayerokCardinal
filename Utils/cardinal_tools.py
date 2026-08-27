from __future__ import annotations
from typing import TYPE_CHECKING

import bcrypt
import requests
import psutil
import json
import sys
import os
import re
import logging
import time
import itertools
from datetime import datetime

if TYPE_CHECKING:
    from cardinal import Cardinal

import PlayerokAPI.types
import Utils.exceptions

logger = logging.getLogger("POC.cardinal_tools")

def count_products(path: str) -> int:
    """
    Считает кол-во товара в указанном файле.

    :param path: путь до файла с товарами.

    :return: кол-во товара в указанном файле.
    """
    if not os.path.exists(path):
        return 0
    with open(path, "r", encoding="utf-8") as f:
        products = f.read()
    products = products.split("\n")
    products = list(itertools.filterfalse(lambda el: not el, products))
    return len(products)

def cache_blacklist(blacklist: list[str]) -> None:
    if not os.path.exists("storage/cache"):
        os.makedirs("storage/cache")
    with open("storage/cache/blacklist.json", "w", encoding="utf-8") as f:
        f.write(json.dumps(blacklist, indent=4))

def load_blacklist() -> list[str]:
    if not os.path.exists("storage/cache/blacklist.json"):
        return []
    with open("storage/cache/blacklist.json", "r", encoding="utf-8") as f:
        blacklist = f.read()
        try:
            blacklist = json.loads(blacklist)
        except json.decoder.JSONDecodeError:
            return []
        return blacklist

def check_proxy(proxy: dict) -> bool:
    from locales.localizer import Localizer
    localizer = Localizer()
    _ = localizer.translate
    
    logger.info(_("crd_checking_proxy"))
    try:
        response = requests.get("https://api.ipify.org?format=json", proxies=proxy, timeout=10)
        ip_address = response.json().get("ip", response.content.decode())
    except requests.exceptions.ProxyError as e:
        # Не логируем ProxyError как ошибку, только в режиме отладки
        logger.debug(f"ProxyError при проверке прокси: {e}")
        logger.debug("TRACEBACK", exc_info=True)
        return False
    except Exception as e:
        logger.error(_("crd_proxy_err"))
        logger.debug(f"Ошибка проверки прокси: {e}")
        logger.debug("TRACEBACK", exc_info=True)
        return False
    logger.info(_("crd_proxy_success", ip_address))
    return True

def validate_proxy(proxy: str):
    proxy = proxy.strip().rstrip("/")
    pattern = (
        r"^((?P<login>[^:]+):(?P<password>[^@]+)@)?"
        r"(?P<host>(?:\d{1,3}\.){3}\d{1,3}|[a-zA-Z0-9](?:[a-zA-Z0-9.-]*[a-zA-Z0-9])?)"
        r":(?P<port>\d+)$"
    )
    result = re.fullmatch(pattern, proxy)
    if not result:
        raise ValueError("Неверный формат прокси.")
    login = result.group("login") or ""
    password = result.group("password") or ""
    host = result.group("host")
    port = result.group("port")
    if re.fullmatch(r"(?:\d{1,3}\.){3}\d{1,3}", host):
        parts = host.split(".")
        if not all(part.isdigit() and 0 <= int(part) < 256 for part in parts):
            raise ValueError("Неправильный IP")
    if not port.isdigit() or not 0 < int(port) <= 65535:
        raise ValueError("Неправильный порт")
    return login, password, host, port


def validate_proxy_url(proxy: str):
    """
    Парсит прокси с поддержкой scheme:// (для Telegram и полных URL).

    :param proxy: прокси
    :return: scheme, login, password, ip, port
    """
    proxy = proxy.strip().rstrip("/")
    if not proxy:
        raise ValueError("Пустая строка прокси")

    if "://" in proxy:
        scheme, rest = proxy.split("://", 1)
    else:
        scheme = "http"
        rest = proxy

    if "@" in rest:
        login_password, host_port = rest.rsplit("@", 1)
        if ":" not in login_password:
            raise ValueError("Неверный формат логина/пароля")
        login, password = login_password.split(":", 1)
    else:
        login, password = "", ""
        host_port = rest

    if ":" not in host_port:
        raise ValueError("Не указан порт")
    host, port = host_port.rsplit(":", 1)
    host = host.strip("[]")

    if re.fullmatch(r"(?:\d{1,3}\.){3}\d{1,3}", host):
        parts = host.split(".")
        if not all(part.isdigit() and 0 <= int(part) < 256 for part in parts):
            raise ValueError("Неправильный IP")
    elif not re.fullmatch(r"[a-zA-Z0-9](?:[a-zA-Z0-9.-]*[a-zA-Z0-9])?", host):
        raise ValueError("Неправильный хост")

    if not port.isdigit() or not 0 < int(port) <= 65535:
        raise ValueError("Неправильный порт")

    if scheme not in ("http", "https", "socks5", "socks5h"):
        raise ValueError("Схема прокси должна быть http, https, socks5 или socks5h")

    return scheme, login, password, host, port


def build_proxy(scheme: str | None, login: str, password: str, ip: str, port: str) -> str:
    if not scheme:
        scheme = "http"
    if login and password:
        return f"{scheme}://{login}:{password}@{ip}:{port}"
    return f"{scheme}://{ip}:{port}"


def resolve_telegram_proxy(main_cfg) -> str | None:
    """Telegram proxy from [Telegram] or fallback to enabled [Proxy] section."""
    tg_proxy = (main_cfg["Telegram"].get("proxy") or "").strip()
    if tg_proxy:
        return tg_proxy

    if main_cfg["Proxy"].get("enable") != "1":
        return None

    ip = (main_cfg["Proxy"].get("ip") or "").strip()
    port = (main_cfg["Proxy"].get("port") or "").strip()
    if not ip or not port:
        return None

    login = (main_cfg["Proxy"].get("login") or "").strip()
    password = (main_cfg["Proxy"].get("password") or "").strip()
    return build_proxy("http", login, password, ip, port)


def hash_password(password: str) -> str:
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')

def check_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))

def set_console_title(title: str) -> None:
    """
    Изменяет название консоли для Windows.
    """
    try:
        if os.name == 'nt':  # Windows
            import ctypes
            ctypes.windll.kernel32.SetConsoleTitleW(title)
    except:
        logger.warning("Произошла ошибка при изменении названия консоли")
        logger.debug("TRACEBACK", exc_info=True)

def cache_proxy_dict(proxy_dict: dict[int, str]) -> None:
    """
    Кэширует список прокси.
    
    :param proxy_dict: список прокси.
    """
    if not os.path.exists("storage/cache"):
        os.makedirs("storage/cache")
    
    with open("storage/cache/proxy_dict.json", "w", encoding="utf-8") as f:
        f.write(json.dumps(proxy_dict, indent=4))

def load_proxy_dict() -> dict[int, str]:
    """
    Загружает список прокси.
    
    :return: список прокси.
    """
    if not os.path.exists("storage/cache/proxy_dict.json"):
        return {}
    
    with open("storage/cache/proxy_dict.json", "r", encoding="utf-8") as f:
        proxy = f.read()
        
        try:
            proxy = json.loads(proxy)
            # Фильтруем только числовые ключи и конвертируем их в int
            result = {}
            for k, v in proxy.items():
                try:
                    key = int(k)
                    result[key] = v
                except (ValueError, TypeError):
                    # Пропускаем нечисловые ключи (например, "http", "https")
                    continue
            return result
        except json.decoder.JSONDecodeError:
            return {}


def cache_disabled_plugins(disabled_plugins: list[str]) -> None:
    """
    Кэширует UUID отключенных плагинов.

    :param disabled_plugins: список UUID отключенных плагинов.
    """
    if not os.path.exists("storage/cache"):
        os.makedirs("storage/cache")

    with open("storage/cache/disabled_plugins.json", "w", encoding="utf-8") as f:
        f.write(json.dumps(disabled_plugins))


def cache_pinned_plugins(pinned_plugins: list[str]) -> None:
    if not os.path.exists("storage/cache"):
        os.makedirs("storage/cache")
    with open("storage/cache/pinned_plugins.json", "w", encoding="utf-8") as f:
        f.write(json.dumps(pinned_plugins))


def load_pinned_plugins() -> list[str]:
    if not os.path.exists("storage/cache/pinned_plugins.json"):
        return []
    with open("storage/cache/pinned_plugins.json", "r", encoding="utf-8") as f:
        try:
            return json.loads(f.read())
        except json.decoder.JSONDecodeError:
            return []


DEFAULT_AUTO_COMPLETE = {
    "enabled": False,
    "all": True,
    "included": [],
    "excluded": [],
}

DEFAULT_AUTO_WITHDRAWAL = {
    "enabled": False,
    "interval": 86400,
    "last_time": "",
    "credentials_type": "",
    "card_id": "",
    "sbp_bank_id": "",
    "sbp_phone_number": "",
    "usdt_address": "",
}

OPTIONAL_MAIN_SECTIONS = {
    "Greetings": {
        "sendGreetings": "0",
        "greetingsText": "Спасибо за покупку! Если нужна помощь — напишите в чат.",
        "greetingsCooldown": "0",
        "ignoreSystemMessages": "1",
        "onlyNewChats": "0",
    },
    "OrderConfirm": {
        "sendReply": "0",
        "watermark": "1",
        "replyText": "Спасибо за подтверждение заказа! Буду рад, если оставите отзыв.",
    },
    "ReviewReply": {
        "sendReply": "0",
        "watermark": "1",
        "reply1": "",
        "reply2": "",
        "reply3": "",
        "reply4": "",
        "reply5": "",
    },
}


def ensure_main_sections(main_cfg: dict) -> bool:
    changed = False
    for section, defaults in OPTIONAL_MAIN_SECTIONS.items():
        if section not in main_cfg:
            main_cfg[section] = dict(defaults)
            changed = True
            continue
        for key, value in defaults.items():
            if key not in main_cfg[section]:
                main_cfg[section][key] = value
                changed = True
    return changed


def load_json_config(path: str, default: dict) -> dict:
    if not os.path.exists(path):
        save_json_config(path, default.copy())
        return default.copy()
    with open(path, "r", encoding="utf-8") as f:
        try:
            data = json.load(f)
        except json.decoder.JSONDecodeError:
            data = default.copy()
            save_json_config(path, data)
            return data
    for key, value in default.items():
        if key not in data:
            data[key] = value
    return data


def save_json_config(path: str, data: dict) -> None:
    directory = os.path.dirname(path)
    if directory and not os.path.exists(directory):
        os.makedirs(directory)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


def ensure_automation_configs() -> None:
    save_json_config("configs/auto_complete.json", load_json_config("configs/auto_complete.json", DEFAULT_AUTO_COMPLETE))
    save_json_config(
        "configs/auto_withdrawal.json",
        load_json_config("configs/auto_withdrawal.json", DEFAULT_AUTO_WITHDRAWAL),
    )


def item_matches_filter(item_name: str, cfg: dict) -> bool:
    """Проверяет, подходит ли название товара под фильтр included/excluded/all."""
    if not item_name:
        return False
    name_lower = item_name.lower()
    excluded = cfg.get("excluded") or []
    included = cfg.get("included") or []
    if any(
        any(phrase.lower() in name_lower or name_lower == phrase.lower() for phrase in group)
        for group in excluded
        if group
    ):
        return False
    if cfg.get("all"):
        return True
    return any(
        any(phrase.lower() in name_lower or name_lower == phrase.lower() for phrase in group)
        for group in included
        if group
    )


def parse_delivery_amount_from_name(item_name: str, default: int = 1) -> int:
    """Парсит количество из названия лота (например «100 шт»)."""
    if not item_name:
        return default
    patterns = [
        r"(\d+)\s*шт",
        r"(\d+)\s*штук",
        r"x\s*(\d+)",
        r"(\d+)\s*pcs",
    ]
    for pattern in patterns:
        match = re.search(pattern, item_name, re.IGNORECASE)
        if match:
            try:
                return max(1, int(match.group(1)))
            except ValueError:
                continue
    return default


def load_disabled_plugins() -> list[str]:
    """
    Загружает список UUID отключенных плагинов из кэша.

    :return: список UUID отключенных плагинов.
    """
    if not os.path.exists("storage/cache/disabled_plugins.json"):
        return []

    with open("storage/cache/disabled_plugins.json", "r", encoding="utf-8") as f:
        try:
            return json.loads(f.read())
        except json.decoder.JSONDecodeError:
            return []


def cache_old_users(old_users: dict[int, float]):
    """
    Сохраняет в кэш список пользователей, которые уже писали на аккаунт.
    """
    if not os.path.exists("storage/cache"):
        os.makedirs("storage/cache")
    with open(f"storage/cache/old_users.json", "w", encoding="utf-8") as f:
        f.write(json.dumps(old_users, ensure_ascii=False))


def load_old_users(greetings_cooldown: float) -> dict[int, float]:
    """
    Загружает из кэша список пользователей, которые уже писали на аккаунт.

    :return: список ID чатов.
    """
    if not os.path.exists(f"storage/cache/old_users.json"):
        return dict()
    with open(f"storage/cache/old_users.json", "r", encoding="utf-8") as f:
        users = f.read()
    try:
        users = json.loads(users)
    except json.decoder.JSONDecodeError:
        return dict()
    # todo убрать позже, конвертация для старых версий кардинала
    if type(users) == list:
        users = {user: time.time() for user in users}
    else:
        users = {int(user): time_ for user, time_ in users.items() if
                 time.time() - time_ < greetings_cooldown * 24 * 60 * 60}
    cache_old_users(users)
    return users


def load_greeting_cache() -> dict[str, float]:
    path = "storage/cache/greeted_chats.json"
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.loads(f.read())
        return {str(k): float(v) for k, v in data.items()}
    except (json.JSONDecodeError, ValueError, TypeError):
        return {}


def save_greeting_cache(cache: dict[str, float]) -> None:
    if not os.path.exists("storage/cache"):
        os.makedirs("storage/cache")
    with open("storage/cache/greeted_chats.json", "w", encoding="utf-8") as f:
        f.write(json.dumps(cache, ensure_ascii=False))


def should_skip_deal_greeting(chat_id: int | str, greetings_cfg: dict) -> bool:
    only_new = greetings_cfg.get("onlyNewChats", "0") == "1"
    try:
        cooldown_days = float(greetings_cfg.get("greetingsCooldown", "0") or "0")
    except ValueError:
        cooldown_days = 0.0
    if not only_new and cooldown_days <= 0:
        return False
    cache = load_greeting_cache()
    last = cache.get(str(chat_id))
    if last is None:
        return False
    if only_new:
        return True
    return time.time() - last < cooldown_days * 86400


def mark_deal_greeting_sent(chat_id: int | str) -> None:
    cache = load_greeting_cache()
    cache[str(chat_id)] = time.time()
    save_greeting_cache(cache)


def _time_greeting() -> str:
    hour = datetime.now().hour
    if hour < 4:
        return "🌙 Доброй ночи"
    if hour < 12:
        return "🌅 Доброе утро"
    if hour < 17:
        return "☀️ Добрый день"
    return "🌆 Добрый вечер"


def create_greeting_text(cardinal: Cardinal) -> str:
    """Приветствие в консоли после авторизации на Playerok."""
    from colorama import Fore, Style

    account = cardinal.account
    balance = cardinal.balance
    W, C, Y, G, R = Fore.WHITE + Style.DIM, Fore.CYAN + Style.BRIGHT, Fore.YELLOW, Fore.GREEN, Style.RESET_ALL

    active_sales = 0
    try:
        profile = getattr(account, "profile", None)
        stats = getattr(profile, "stats", None) if profile else None
        deals = getattr(stats, "deals", None) if stats else None
        incoming = getattr(deals, "incoming", None) if deals else None
        if incoming:
            active_sales = getattr(incoming, "total", 0) or 0
    except Exception:
        pass

    balance_rub = balance.value if balance.value else 0
    greeting = _time_greeting()
    username = account.username
    user_id = account.id

    return (
        f"\n{W}╭────────────────────────────────────────────────────╮{R}\n"
        f"{W}│{R}  {greeting}, {C}{username}{R}\n"
        f"{W}│{R}\n"
        f"{W}│{R}  {W}ID{R}      {Y}{user_id}{R}\n"
        f"{W}│{R}  {W}Баланс{R}  {C}{balance_rub:.2f} ₽{R}\n"
        f"{W}│{R}  {W}Сделки{R}  {Y}{active_sales}{R} в работе\n"
        f"{W}│{R}\n"
        f"{W}│{R}  {G}Удачной торговли!{R}\n"
        f"{W}╰────────────────────────────────────────────────────╯{R}\n"
    )


def time_to_str(time_: int):
    """
    Конвертирует число в строку формата "Хд Хч Хмин Хсек"

    :param time_: число для конвертации.

    :return: строку-время.
    """
    days = time_ // 86400
    hours = (time_ - days * 86400) // 3600
    minutes = (time_ - days * 86400 - hours * 3600) // 60
    seconds = time_ - days * 86400 - hours * 3600 - minutes * 60

    if not any([days, hours, minutes, seconds]):  # locale
        return "0 сек"
    time_str = ""
    if days:
        time_str += f"{days}д"
    if hours:
        time_str += f" {hours}ч"
    if minutes:
        time_str += f" {minutes}мин"
    if seconds:
        time_str += f" {seconds}сек"
    return time_str.strip()


def get_month_name(month_number: int) -> str:
    """
    Возвращает название месяца в родительном падеже.

    :param month_number: номер месяца.

    :return: название месяца в родительном падеже.
    """
    months = [
        "Января", "Февраля", "Марта",
        "Апреля", "Мая", "Июня",
        "Июля", "Августа", "Сентября",
        "Октября", "Ноября", "Декабря"
    ]  # todo локализация
    if month_number > len(months):
        return months[0]
    return months[month_number - 1]


def get_products(path: str, amount: int = 1) -> list[list[str] | int] | None:
    """
    Берет из товарного файла товар/-ы, удаляет их из товарного файла.

    :param path: путь до файла с товарами.
    :param amount: кол-во товара.

    :return: [[Товар/-ы], оставшееся кол-во товара]
    """
    with open(path, "r", encoding="utf-8") as f:
        products = f.read()

    products = products.split("\n")

    # Убираем пустые элементы
    products = list(itertools.filterfalse(lambda el: not el, products))

    if not products:
        raise Utils.exceptions.NoProductsError(path)

    elif len(products) < amount:
        raise Utils.exceptions.NotEnoughProductsError(path, len(products), amount)

    got_products = products[:amount]
    save_products = products[amount:]
    amount = len(save_products)

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(save_products))

    return [got_products, amount]


def add_products(path: str, products: list[str], at_zero_position=False):
    """
    Добавляет товары в файл с товарами.

    :param path: путь до файла с товарами.
    :param products: товары.
    :param at_zero_position: добавить товары в начало товарного файла.
    """
    if not at_zero_position:
        with open(path, "a", encoding="utf-8") as f:
            f.write("\n" + "\n".join(products))
    else:
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(products) + "\n" + text)


def safe_text(text: str):
    return "⁣".join(text)


def format_msg_text(text: str, obj: PlayerokAPI.types.ChatMessage | PlayerokAPI.types.Chat) -> str:
    """
    Форматирует текст, подставляя значения переменных, доступных для MessageEvent.

    :param text: текст для форматирования.
    :param obj: экземпляр types.ChatMessage или types.Chat.

    :return: форматированый текст.
    """
    date_obj = datetime.now()
    month_name = get_month_name(date_obj.month)
    date = date_obj.strftime("%d.%m.%Y")
    str_date = f"{date_obj.day} {month_name}"
    str_full_date = str_date + f" {date_obj.year} года"  # locale

    time_ = date_obj.strftime("%H:%M")
    time_full = date_obj.strftime("%H:%M:%S")

    if isinstance(obj, PlayerokAPI.types.ChatMessage):
        username = obj.user.username if hasattr(obj.user, 'username') else str(obj.user.id)
        chat_name = obj.chat.id if hasattr(obj, 'chat') and obj.chat else ""
        chat_id = obj.chat.id if hasattr(obj, 'chat') and obj.chat else ""
    else:  # Chat
        username = obj.users[0].username if obj.users and hasattr(obj.users[0], 'username') else str(obj.users[0].id) if obj.users else ""
        chat_name = obj.id
        chat_id = obj.id

    variables = {
        "$full_date_text": str_full_date,
        "$date_text": str_date,
        "$date": date,
        "$time": time_,
        "$full_time": time_full,
        "$username": safe_text(username),
        "$message_text": str(obj),
        "$chat_id": str(chat_id),
        "$chat_name": safe_text(chat_name)
    }

    for var in variables:
        text = text.replace(var, variables[var])
    return text


def format_deal_props(props) -> str:
    if not props:
        return ""
    if isinstance(props, str):
        return props
    period = getattr(props, "auto_confirm_period", None)
    if period is not None:
        return f"Авто-подтверждение: {period} дн."
    return str(props)


def format_order_text(text: str, order: PlayerokAPI.types.ItemDeal) -> str:
    """
    Форматирует текст, подставляя значения переменных, доступных для Order.

    :param text: текст для форматирования.
    :param order: экземпляр ItemDeal.

    :return: форматированый текст.
    """
    date_obj = datetime.now()
    month_name = get_month_name(date_obj.month)
    date = date_obj.strftime("%d.%m.%Y")
    str_date = f"{date_obj.day} {month_name}"
    str_full_date = str_date + f" {date_obj.year} года"  # locale
    time_ = date_obj.strftime("%H:%M")
    time_full = date_obj.strftime("%H:%M:%S")
    game = subcategory_fullname = subcategory = ""
    try:
        if hasattr(order.item, 'category') and order.item.category:
            subcategory_fullname = order.item.category.name if hasattr(order.item.category, 'name') else ""
            game = order.item.category.game.name if hasattr(order.item.category, 'game') and order.item.category.game else ""
            subcategory = order.item.category.name if hasattr(order.item.category, 'name') else ""
    except:
        logger.warning("Произошла ошибка при парсинге игры из заказа")  # locale
        logger.debug("TRACEBACK", exc_info=True)
    description = order.item.name if hasattr(order.item, 'name') else ""
    params = format_deal_props(order.props if hasattr(order, 'props') else "")
    # В PlayerokAPI для ItemDeal используется user (покупатель/продавец сделки)
    if hasattr(order, 'user') and order.user:
        username = order.user.username if hasattr(order.user, 'username') else str(order.user.id)
    else:
        username = ""
    variables = {
        "$full_date_text": str_full_date,
        "$date_text": str_date,
        "$date": date,
        "$time": time_,
        "$full_time": time_full,
        "$username": safe_text(username),
        "$order_desc_and_params": f"{description}, {params}" if description and params else f"{description}{params}",
        "$order_desc_or_params": description if description else params,
        "$order_desc": description,
        "$order_title": description,
        "$order_params": params,
        "$order_id": str(order.id),
        "$order_link": f"https://playerok.com/deals/{order.id}/",
        "$category_fullname": subcategory_fullname,
        "$category": subcategory,
        "$game": game
    }

    for var in variables:
        text = text.replace(var, str(variables[var]))
    return text


def restart_program():
    """
    Полный перезапуск POC.
    """
    python = sys.executable
    os.execl(python, python, *sys.argv)
    try:
        process = psutil.Process()
        for handler in process.open_files():
            os.close(handler.fd)
        for handler in process.connections():
            os.close(handler.fd)
    except:
        pass


def shut_down():
    """
    Полное отключение POC.
    """
    try:
        process = psutil.Process()
        process.terminate()
    except:
        pass


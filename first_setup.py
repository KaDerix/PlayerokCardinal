import os
from configparser import ConfigParser
import time
import telebot
from colorama import Fore, Style
from Utils.cardinal_tools import validate_proxy, validate_proxy_url, build_proxy, check_proxy, hash_password
from Utils.config_loader import create_config_obj, load_main_config

default_config = {
    "Playerok": {
        "token": "",
        "ddg5": "",
        "cookies": "",
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36",
        "autoResponse": "0",
        "autoDelivery": "0",
        "autoRestore": "0",
        "autoRaise": "0",
        "multiDelivery": "0",
        "autoDisable": "0",
        "autoCompleteDeals": "0",
        "autoWithdrawal": "0",
        "restorePriorityMode": "premium",
        "oldMsgGetMode": "0",
        "keepSentMessagesUnread": "0"
    },
    "Telegram": {
        "enabled": "0",
        "token": "",
        "secretKeyHash": "ХешСекретногоПароля",
        "proxy": "",
        "blockLogin": "0"
    },
    "Proxy": {
        "enable": "0",
        "ip": "",
        "port": "",
        "login": "",
        "password": "",
        "check": "0"
    },
    "Other": {
        "watermark": "🎮",
        "requestsDelay": "4"
    }
}

def create_configs():
    if not os.path.exists("configs/auto_response.cfg"):
        with open("configs/auto_response.cfg", "w", encoding="utf-8"):
            ...
    if not os.path.exists("configs/auto_delivery.cfg"):
        with open("configs/auto_delivery.cfg", "w", encoding="utf-8"):
            ...

def create_config_obj(settings) -> ConfigParser:
    config = ConfigParser(delimiters=(":",), interpolation=None)
    config.optionxform = str
    config.read_dict(settings)
    return config

def contains_russian(text: str) -> bool:
    for char in text:
        if 'А' <= char <= 'я' or char in 'Ёё':
            return True
    return False


def input_proxy(set_telebot_proxy: bool = False) -> str | None:
    while True:
        proxy_input = input(f"{Fore.MAGENTA}{Style.BRIGHT}└───> {Style.RESET_ALL}").strip()

        if not proxy_input:
            if set_telebot_proxy:
                telebot.apihelper.proxy = None
            return None

        try:
            scheme, login, password, ip, port = validate_proxy_url(proxy_input)
            proxy = build_proxy(scheme, login, password, ip, port)

            if not check_proxy({"http": proxy, "https": proxy}):
                print("\nНевалидные прокси. Попробуй еще раз!")
                continue

            if set_telebot_proxy:
                telebot.apihelper.proxy = {"http": proxy, "https": proxy}

            return proxy

        except Exception as ex:
            print(f"\nНеверный формат прокси: {ex}. Попробуй еще раз!")


def setup_telegram_proxy():
    cfg_path = "configs/_main.cfg"
    main_cfg = load_main_config(cfg_path)
    config = create_config_obj(cfg_path)
    print(
        f"\n{Fore.MAGENTA}{Style.BRIGHT}┌── {Fore.CYAN}"
        f"Если хочешь использовать IPv4 прокси ДЛЯ ДОСТУПА К TELEGRAM"
        f" – укажи их в формате scheme://login:password@ip:port, login:password@ip:port или ip:port."
        f" Если ты не знаешь, что это такое или они тебе не нужны - просто нажми Enter. "
        f"{Fore.RED}(* ^ ω ^){Style.RESET_ALL}")
    while True:
        try:
            proxy = input_proxy(set_telebot_proxy=True)
            username = telebot.TeleBot(main_cfg["Telegram"]["token"]).get_me().username
            print(f"\n\n{Fore.CYAN}Подключение к Telegram успешно: @{username}...{Style.RESET_ALL}")
            break
        except Exception as ex:
            print(f"\n\n{Fore.CYAN}Не удалось добавить прокси: {ex}...{Style.RESET_ALL}")

    config.set("Telegram", "proxy", proxy or "")
    print(f"{Fore.CYAN}Сохраняю конфиг...{Style.RESET_ALL}")
    with open(cfg_path, "w", encoding="utf-8") as f:
        config.write(f)
    time.sleep(5)


def first_setup():
    import colorama
    colorama.init()
    
    config = create_config_obj(default_config)
    sleep_time = 1

    print(f"\n{Fore.CYAN}{Style.BRIGHT}Привет! {Fore.RED}(`-`)/{Style.RESET_ALL}")
    time.sleep(sleep_time)

    print(f"\n{Fore.CYAN}{Style.BRIGHT}Не могу найти основной конфиг... {Fore.RED}(-_-;). . .{Style.RESET_ALL}")
    time.sleep(sleep_time)

    print(f"\n{Fore.CYAN}{Style.BRIGHT}Давай ка проведем первичную настройку! {Fore.RED}°++°{Style.RESET_ALL}")
    time.sleep(sleep_time)

    while True:
        print(f"\n{Fore.MAGENTA}{Style.BRIGHT}┌── {Fore.CYAN}"
              f"Введи токен (token) твоего Playerok аккаунта (можно найти в Cookie) {Fore.RED}(._.){Style.RESET_ALL}")
        token = input(f"{Fore.MAGENTA}{Style.BRIGHT}└───> {Style.RESET_ALL}").strip()
        if len(token) > 10:
            config.set("Playerok", "token", token)
            break
        else:
            print(f"\n{Fore.CYAN}{Style.BRIGHT}Неверный формат токена. Попробуй еще раз! {Fore.RED}\\(!!˚0˚)/{Style.RESET_ALL}")

    while True:
        print(f"\n{Fore.MAGENTA}{Style.BRIGHT}┌── {Fore.CYAN}"
              f"Если хочешь, можешь указать свой User-agent (введи в Google \"my user agent\"). Или просто нажми Enter. "
              f"{Fore.RED}¯\\(°_o)/¯{Style.RESET_ALL}")
        user_agent = input(f"{Fore.MAGENTA}{Style.BRIGHT}└───> {Style.RESET_ALL}").strip()
        if contains_russian(user_agent):
            print(f"\n{Fore.CYAN}{Style.BRIGHT}Ты не знаешь, что такое Google? {Fore.RED}\\(!!˚0˚)/{Style.RESET_ALL}")
            continue
        if user_agent:
            config.set("Playerok", "user_agent", user_agent)
        break

    print(f"\n{Fore.MAGENTA}{Style.BRIGHT}┌── {Fore.CYAN}"
          f"Если хочешь использовать IPv4 прокси ДЛЯ ДОСТУПА К TELEGRAM"
          f" – укажи их в формате scheme://login:password@ip:port, login:password@ip:port или ip:port."
          f" Если ты не знаешь, что это такое или они тебе не нужны - просто нажми Enter. "
          f"{Fore.RED}(* ^ ω ^){Style.RESET_ALL}")
    tg_proxy = input_proxy(set_telebot_proxy=True)
    if tg_proxy:
        config.set("Telegram", "proxy", tg_proxy)

    while True:
        print(
            f"\n{Fore.MAGENTA}{Style.BRIGHT}┌── {Fore.CYAN}Введи API-токен Telegram-бота (получить можно у @BotFather). "
            f"@username бота должен начинаться с \"playerok\". {Fore.RED}(._.){Style.RESET_ALL}")
        token = input(f"{Fore.MAGENTA}{Style.BRIGHT}└───> {Style.RESET_ALL}").strip()
        try:
            if not token or not token.split(":")[0].isdigit():
                raise Exception("Неправильный формат токена")
            username = telebot.TeleBot(token).get_me().username
            if not username.lower().startswith("playerok"):
                print(f"\n{Fore.CYAN}{Style.BRIGHT}@username бота должен начинаться с \"playerok\"! {Fore.RED}\\(!!˚0˚)/{Style.RESET_ALL}")
                continue
        except Exception as ex:
            s = ""
            if str(ex):
                s = f" ({str(ex)})"
            print(f"\n{Fore.CYAN}{Style.BRIGHT}Попробуй еще раз!{s} {Fore.RED}\\(!!˚0˚)/{Style.RESET_ALL}")
            continue
        break

    while True:
        print(
            f"\n{Fore.MAGENTA}{Style.BRIGHT}┌── {Fore.CYAN}Придумай пароль (его потребует Telegram-бот). Пароль должен содержать более 8 символов, заглавные, строчные буквы и хотя бы одну цифру "
            f" {Fore.RED}ᴖ̮ ̮ᴖ{Style.RESET_ALL}")
        password = input(f"{Fore.MAGENTA}{Style.BRIGHT}└───> {Style.RESET_ALL}").strip()
        if len(password) < 8 or password.lower() == password or password.upper() == password or not any([i.isdigit() for i in password]):
            print(f"\n{Fore.CYAN}{Style.BRIGHT}Это плохой пароль. Попробуй еще раз! {Fore.RED}\\(!!˚0˚)/{Style.RESET_ALL}")
            continue
        break

    config.set("Telegram", "enabled", "1")
    config.set("Telegram", "token", token)
    config.set("Telegram", "secretKeyHash", hash_password(password))

    while True:
        print(f"\n{Fore.MAGENTA}{Style.BRIGHT}┌── {Fore.CYAN}"
              f"Если хочешь использовать IPv4 прокси – укажи их в формате login:password@ip:port или ip:port. Если не нужны - просто нажми Enter. "
              f"{Fore.RED}(* ^ ω ^){Style.RESET_ALL}")
        proxy = input(f"{Fore.MAGENTA}{Style.BRIGHT}└───> {Style.RESET_ALL}").strip()
        if proxy:
            try:
                login, password, ip, port = validate_proxy(proxy)
                config.set("Proxy", "enable", "1")
                config.set("Proxy", "check", "1")
                config.set("Proxy", "login", login)
                config.set("Proxy", "password", password)
                config.set("Proxy", "ip", ip)
                config.set("Proxy", "port", port)
                break
            except:
                print(f"\n{Fore.CYAN}{Style.BRIGHT}Неверный формат прокси. Попробуй еще раз! {Fore.RED}(o-_-o){Style.RESET_ALL}")
                continue
        else:
            break

    if not os.path.exists("configs"):
        os.makedirs("configs")
    
    print(f"\n{Fore.CYAN}{Style.BRIGHT}Готово! Сейчас я сохраню конфиг и завершу программу! {Fore.RED}ʘ>ʘ{Style.RESET_ALL}")
    print(f"{Fore.CYAN}{Style.BRIGHT}Запусти меня снова и напиши своему Telegram-боту. "
          f"Все остальное ты сможешь настроить через него. {Fore.RED}ʕ•ᴥ•ʔ{Style.RESET_ALL}")
    
    with open("configs/_main.cfg", "w", encoding="utf-8") as f:
        config.write(f)
    
    print(f"\n{Fore.GREEN}{Style.BRIGHT}✓ Конфиг сохранен в configs/_main.cfg{Style.RESET_ALL}")
    print(f"{Fore.YELLOW}{Style.BRIGHT}Программа завершится через 5 секунд...{Style.RESET_ALL}")
    time.sleep(5)



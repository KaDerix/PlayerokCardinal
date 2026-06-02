import time
from pip._internal.cli.main import main

# Устанавливаем зависимости перед импортом Utils.cardinal_tools
while True:
    try:
        import lxml
        break
    except ModuleNotFoundError:
        main(["install", "-U", "lxml>=5.2.2"])

while True:
    try:
        import bcrypt
        break
    except ModuleNotFoundError:
        main(["install", "-U", "bcrypt>=4.2.0"])

while True:
    try:
        import psutil
        break
    except ModuleNotFoundError:
        main(["install", "-U", "psutil>=5.9.4"])

import Utils.cardinal_tools
import Utils.config_loader as cfg_loader
from first_setup import first_setup
from colorama import Fore, Style
from Utils.logger import LOGGER_CONFIG
import logging.config
import colorama
import sys
import os
from cardinal import Cardinal
import Utils.exceptions as excs

logo = """\033[38;5;0m.\033[0m\033[38;5;0m.\033[0m\033[38;5;0m.\033[0m\033[38;5;0m.\033[0m\033[38;5;0m.\033[0m\033[38;5;0m.\033[0m\033[38;5;0m.\033[0m\033[38;5;0m.\033[0m\033[38;5;0m.\033[0m\033[38;5;0m.\033[0m\033[38;5;0m.\033[0m\033[38;5;0m.\033[0m\033[38;5;0m.\033[0m\033[38;5;0m.\033[0m\033[38;5;0m.\033[0m\033[38;5;0m.\033[0m\033[38;5;0m.\033[0m\033[38;5;0m.\033[0m\033[38;5;0m.\033[0m\033[38;5;0m.\033[0m\033[38;5;0m.\033[0m\033[38;5;0m.\033[0m
\033[38;5;0m.\033[0m\033[38;5;0m.\033[0m\033[38;5;52m>\033[0m\033[38;5;88m|\033[0m\033[38;5;124m}\033[0m\033[38;5;124m]\033[0m\033[38;5;124m]\033[0m\033[38;5;88m?\033[0m\033[38;5;88m?\033[0m\033[38;5;124m+\033[0m\033[38;5;124m+\033[0m\033[38;5;124m+\033[0m\033[38;5;124m+\033[0m\033[38;5;88m?\033[0m\033[38;5;88m?\033[0m\033[38;5;124m]\033[0m\033[38;5;124m]\033[0m\033[38;5;124m]\033[0m\033[38;5;88m|\033[0m\033[38;5;52m>\033[0m\033[38;5;0m.\033[0m\033[38;5;0m.\033[0m
\033[38;5;0m.\033[0m\033[38;5;0m'\033[0m\033[38;5;15mP\033[0m\033[38;5;15mL\033[0m\033[38;5;15mA\033[0m\033[38;5;15mY\033[0m\033[38;5;15mE\033[0m\033[38;5;15mR\033[0m\033[38;5;15mO\033[0m\033[38;5;15mK\033[0m\033[38;5;0m \033[0m\033[38;5;15mC\033[0m\033[38;5;15mA\033[0m\033[38;5;15mR\033[0m\033[38;5;15mD\033[0m\033[38;5;15mI\033[0m\033[38;5;15mN\033[0m\033[38;5;15mA\033[0m\033[38;5;15mL\033[0m\033[38;5;0m'\033[0m\033[38;5;0m.\033[0m
\033[38;5;0m.\033[0m\033[38;5;0m.\033[0m\033[38;5;52m>\033[0m\033[38;5;88m|\033[0m\033[38;5;124m]\033[0m\033[38;5;124m]\033[0m\033[38;5;124m+\033[0m\033[38;5;88m?\033[0m\033[38;5;88m?\033[0m\033[38;5;124m+\033[0m\033[38;5;124m+\033[0m\033[38;5;124m+\033[0m\033[38;5;124m+\033[0m\033[38;5;88m?\033[0m\033[38;5;88m?\033[0m\033[38;5;124m+\033[0m\033[38;5;124m]\033[0m\033[38;5;124m]\033[0m\033[38;5;88m|\033[0m\033[38;5;52m>\033[0m\033[38;5;0m.\033[0m\033[38;5;0m.\033[0m
\033[38;5;0m.\033[0m\033[38;5;0m.\033[0m\033[38;5;0m.\033[0m\033[38;5;0m.\033[0m\033[38;5;0m.\033[0m\033[38;5;0m.\033[0m\033[38;5;0m.\033[0m\033[38;5;0m.\033[0m\033[38;5;0m.\033[0m\033[38;5;0m.\033[0m\033[38;5;0m.\033[0m\033[38;5;0m.\033[0m\033[38;5;0m.\033[0m\033[38;5;0m.\033[0m\033[38;5;0m.\033[0m\033[38;5;0m.\033[0m\033[38;5;0m.\033[0m\033[38;5;0m.\033[0m\033[38;5;0m.\033[0m\033[38;5;0m.\033[0m\033[38;5;0m.\033[0m"""

VERSION = "1.0.9"

Utils.cardinal_tools.set_console_title(f"Playerok Cardinal v{VERSION}")

if getattr(sys, 'frozen', False):
    os.chdir(os.path.dirname(sys.executable))
else:
    os.chdir(os.path.dirname(__file__))

folders = ["configs", "logs", "storage", "storage/cache", "storage/products", "plugins"]
for i in folders:
    if not os.path.exists(i):
        os.makedirs(i)

files = ["configs/auto_delivery.cfg", "configs/auto_response.cfg"]
for i in files:
    if not os.path.exists(i):
        with open(i, "w", encoding="utf-8") as f:
            ...

import Utils.cardinal_tools as _ct
_ct.ensure_automation_configs()

colorama.init()

logging.config.dictConfig(LOGGER_CONFIG)
logging.raiseExceptions = False
logger = logging.getLogger("main")
logger.debug("------------------------------------------------------------------")

print(f"{Style.RESET_ALL}{logo}")
print(f"{Fore.RED}{Style.BRIGHT}v{VERSION}{Style.RESET_ALL}\n")
print(f"{Fore.MAGENTA}{Style.BRIGHT}By {Fore.CYAN}{Style.BRIGHT}@KaDerix{Style.RESET_ALL}")
print(f"{Fore.MAGENTA}{Style.BRIGHT} * GitHub: {Fore.CYAN}{Style.BRIGHT}github.com/KITUSTTT/PlayerokCardinal{Style.RESET_ALL}")
print(f"{Fore.MAGENTA}{Style.BRIGHT} * Telegram: {Fore.CYAN}{Style.BRIGHT}t.me/KaDerix{Style.RESET_ALL}")

if not os.path.exists("configs/_main.cfg"):
    first_setup()
    sys.exit()

if sys.platform == "linux" and os.getenv('POC_IS_RUNNING_AS_SERVICE', '0') == '1':
    import getpass
    pid = str(os.getpid())
    pidFile = open(f"/run/PlayerokCardinal/{getpass.getuser()}/PlayerokCardinal.pid", "w")
    pidFile.write(pid)
    pidFile.close()
    logger.info(f"$GREENPID файл создан, PID процесса: {pid}")

try:
    logger.info("$MAGENTAЗагружаю конфиг _main.cfg...")
    MAIN_CFG = cfg_loader.load_main_config("configs/_main.cfg")

    logger.info("$MAGENTAЗагружаю конфиг auto_response.cfg...")
    AR_CFG = cfg_loader.load_auto_response_config("configs/auto_response.cfg")
    RAW_AR_CFG = cfg_loader.load_raw_auto_response_config("configs/auto_response.cfg")

    logger.info("$MAGENTAЗагружаю конфиг auto_delivery.cfg...")
    AD_CFG = cfg_loader.load_auto_delivery_config("configs/auto_delivery.cfg")
except excs.ConfigParseError as e:
    logger.error(e)
    logger.error("Завершаю программу...")
    time.sleep(5)
    sys.exit()
except UnicodeDecodeError:
    logger.error("Произошла ошибка при расшифровке UTF-8. Убедитесь, что кодировка файла = UTF-8, а формат конца строк = LF.")
    logger.error("Завершаю программу...")
    time.sleep(5)
    sys.exit()
except:
    logger.critical("Произошла непредвиденная ошибка.")
    logger.warning("TRACEBACK", exc_info=True)
    logger.error("Завершаю программу...")
    time.sleep(5)
    sys.exit()

try:
    Cardinal(MAIN_CFG, AD_CFG, AR_CFG, RAW_AR_CFG, VERSION).init().run()
except KeyboardInterrupt:
    logger.info("Завершаю программу...")
    sys.exit()
except:
    logger.critical("При работе Cardinal произошла необработанная ошибка.")
    logger.warning("TRACEBACK", exc_info=True)
    logger.critical("Завершаю программу...")
    time.sleep(5)
    sys.exit()

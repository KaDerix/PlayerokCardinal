from __future__ import annotations
from typing import TYPE_CHECKING, Callable
from threading import Thread

if TYPE_CHECKING:
    from configparser import ConfigParser

import PlayerokAPI
from PlayerokAPI.listener.listener import EventListener
from PlayerokAPI.listener.events import *
from Utils import cardinal_tools
import handlers
import logging
import time
import sys
import os
import importlib.util
from types import ModuleType
from uuid import UUID

logger = logging.getLogger("POC")

def get_cardinal() -> None | Cardinal:
    if hasattr(Cardinal, "instance"):
        return getattr(Cardinal, "instance")


class PluginData:
    """
    Класс, описывающий плагин.
    """

    def __init__(self, name: str, version: str, desc: str, credentials: str, uuid: str,
                 path: str, plugin: ModuleType, settings_page: bool, delete_handler: Callable | None, enabled: bool,
                 pinned: bool = False):
        """
        :param name: название плагина.
        :param version: версия плагина.
        :param desc: описание плагина.
        :param credentials: авторы плагина.
        :param uuid: UUID плагина.
        :param path: путь до плагина.
        :param plugin: экземпляр плагина как модуля.
        :param settings_page: есть ли страница настроек у плагина.
        :param delete_handler: хэндлер, привязанный к удалению плагина.
        :param enabled: включен ли плагин.
        """
        self.name = name
        self.version = version
        self.description = desc
        self.credits = credentials
        self.uuid = uuid

        self.path = path
        self.plugin = plugin
        self.settings_page = settings_page
        self.commands = {}
        self.delete_handler = delete_handler
        self.enabled = enabled
        self.pinned = pinned


class Cardinal(object):
    def __new__(cls, *args, **kwargs):
        if not hasattr(cls, "instance"):
            cls.instance = super(Cardinal, cls).__new__(cls)
        return getattr(cls, "instance")

    def __init__(self, main_config: ConfigParser,
                 auto_delivery_config: list,
                 auto_response_config: dict,
                 raw_auto_response_config: ConfigParser,
                 version: str):
        self.VERSION = version
        
        self.MAIN_CFG = main_config
        self.AD_CFG = auto_delivery_config
        self.AR_CFG = auto_response_config
        self.RAW_AR_CFG = raw_auto_response_config
        
        self.proxy = None
        self.proxy_dict = cardinal_tools.load_proxy_dict()
        if self.MAIN_CFG["Proxy"].get("enable") == "1":
            if self.MAIN_CFG["Proxy"]["ip"] and self.MAIN_CFG["Proxy"]["port"].isnumeric():
                from locales.localizer import Localizer
                language = self.MAIN_CFG.get("Other", {}).get("language", "ru")
                localizer = Localizer(language)
                _ = localizer.translate
                logger.info(_("crd_proxy_detected"))
                logger.info(_("crd_checking_proxy"))
                ip, port = self.MAIN_CFG["Proxy"]["ip"], self.MAIN_CFG["Proxy"]["port"]
                login, password = self.MAIN_CFG["Proxy"]["login"], self.MAIN_CFG["Proxy"]["password"]
                proxy_str = f"{f'{login}:{password}@' if login and password else ''}{ip}:{port}"
                proxy_dict_for_check = {
                    "http": f"http://{proxy_str}",
                    "https": f"http://{proxy_str}"
                }
                self.proxy = proxy_str
                
                if proxy_str not in self.proxy_dict.values():
                    max_id = max(self.proxy_dict.keys(), default=-1) if self.proxy_dict else -1
                    self.proxy_dict[max_id + 1] = proxy_str
                    cardinal_tools.cache_proxy_dict(self.proxy_dict)
                
                if self.MAIN_CFG["Proxy"].get("check") == "1":
                    if not cardinal_tools.check_proxy(proxy_dict_for_check):
                        logger.error(_("crd_proxy_err"))
                        sys.exit()
                    else:
                        import requests
                        try:
                            response = requests.get("https://api.ipify.org?format=json", proxies=proxy_dict_for_check, timeout=10)
                            ip_address = response.json().get("ip", "unknown")
                            logger.info(_("crd_proxy_success", ip_address))
                        except:
                            pass

        pk_cfg = self.MAIN_CFG["Playerok"]
        cookies = pk_cfg.get("cookies", "").strip()
        self.account = PlayerokAPI.Account(
            token=pk_cfg["token"],
            ddg5=pk_cfg.get("ddg5", "").strip(),
            cookies=cookies if cookies else None,
            user_agent=pk_cfg["user_agent"],
            proxy=self.proxy
        )
        
        self.listener: EventListener | None = None
        self.telegram: "tg_bot.bot.TGBot" | None = None
        
        self.running = False
        self.run_id = 0
        self.start_time = int(time.time())
        self.instance_id = id(self)
        self.blacklist = cardinal_tools.load_blacklist()
        self.tg_profile = None
        self.last_tg_profile_update = None
        
        pk = self.MAIN_CFG["Playerok"]
        cardinal_tools.ensure_automation_configs()
        self.auto_bump_cfg = cardinal_tools.load_json_config("configs/auto_bump.json", cardinal_tools.DEFAULT_AUTO_BUMP)
        self.auto_complete_cfg = cardinal_tools.load_json_config(
            "configs/auto_complete.json", cardinal_tools.DEFAULT_AUTO_COMPLETE
        )
        self.auto_withdrawal_cfg = cardinal_tools.load_json_config(
            "configs/auto_withdrawal.json", cardinal_tools.DEFAULT_AUTO_WITHDRAWAL
        )
        self._init_handlers_and_plugins()
        logger.info(
            f"⚙️ Настройки: autoResponse={self.autoresponse_enabled}, autoDelivery={self.autodelivery_enabled}, "
            f"autoRestore={self.autorestore_enabled}, autoRaise={self.autoraise_enabled}, "
            f"multiDelivery={self.multidelivery_enabled}, autoDisable={self.autodisable_enabled}, "
            f"autoComplete={self.autocomplete_enabled}, autoWithdrawal={self.autowithdrawal_enabled}"
        )

    def _pk_flag(self, key: str) -> bool:
        return self.MAIN_CFG.get("Playerok", {}).get(key, "0") == "1"

    @property
    def autoresponse_enabled(self) -> bool:
        return self._pk_flag("autoResponse")

    @property
    def autodelivery_enabled(self) -> bool:
        return self._pk_flag("autoDelivery")

    @property
    def autorestore_enabled(self) -> bool:
        return self._pk_flag("autoRestore")

    @property
    def autoraise_enabled(self) -> bool:
        return self._pk_flag("autoRaise")

    @property
    def multidelivery_enabled(self) -> bool:
        return self._pk_flag("multiDelivery")

    @property
    def autodisable_enabled(self) -> bool:
        return self._pk_flag("autoDisable")

    @property
    def autocomplete_enabled(self) -> bool:
        return self._pk_flag("autoCompleteDeals")

    @property
    def autowithdrawal_enabled(self) -> bool:
        return self._pk_flag("autoWithdrawal")

    def _init_handlers_and_plugins(self):  # noqa: PLR0915
        self.pre_init_handlers = []
        self.post_init_handlers = []
        self.pre_start_handlers = []
        self.post_start_handlers = []
        self.pre_stop_handlers = []
        self.post_stop_handlers = []

        self.new_message_handlers = []
        self.new_order_handlers = []
        self.chat_initialized_handlers = []
        self.new_deal_handlers = []
        self.item_paid_handlers = []
        self.item_sent_handlers = []
        self.deal_confirmed_handlers = []
        self.new_review_handlers = []
        self.deal_rolled_back_handlers = []
        self.deal_has_problem_handlers = []
        self.deal_problem_resolved_handlers = []
        self.deal_status_changed_handlers = []

        self.balance = None

        self.plugins: dict[str, PluginData] = {}
        self.disabled_plugins = cardinal_tools.load_disabled_plugins()
        self.pinned_plugins = cardinal_tools.load_pinned_plugins()
        self._automation_threads_started = False

        self.handler_bind_var_names = {
            "BIND_TO_PRE_INIT": self.pre_init_handlers,
            "BIND_TO_POST_INIT": self.post_init_handlers,
            "BIND_TO_PRE_START": self.pre_start_handlers,
            "BIND_TO_POST_START": self.post_start_handlers,
            "BIND_TO_PRE_STOP": self.pre_stop_handlers,
            "BIND_TO_POST_STOP": self.post_stop_handlers,
            "BIND_TO_NEW_MESSAGE": self.new_message_handlers,
            "BIND_TO_NEW_ORDER": self.new_order_handlers,
            "BIND_TO_CHAT_INITIALIZED": self.chat_initialized_handlers,
            "BIND_TO_NEW_DEAL": self.new_deal_handlers,
            "BIND_TO_ITEM_PAID": self.item_paid_handlers,
            "BIND_TO_ITEM_SENT": self.item_sent_handlers,
            "BIND_TO_DEAL_CONFIRMED": self.deal_confirmed_handlers,
            "BIND_TO_NEW_REVIEW": self.new_review_handlers,
            "BIND_TO_DEAL_ROLLED_BACK": self.deal_rolled_back_handlers,
            "BIND_TO_DEAL_HAS_PROBLEM": self.deal_has_problem_handlers,
            "BIND_TO_DEAL_PROBLEM_RESOLVED": self.deal_problem_resolved_handlers,
            "BIND_TO_DEAL_STATUS_CHANGED": self.deal_status_changed_handlers,
        }

    def get_balance(self):
        """Получает баланс аккаунта"""
        try:
            if hasattr(self.account, 'profile') and self.account.profile:
                if hasattr(self.account.profile, 'balance') and self.account.profile.balance:
                    return self.account.profile.balance
            self.account.get()
            if hasattr(self.account, 'profile') and self.account.profile and hasattr(self.account.profile, 'balance'):
                return self.account.profile.balance
            from PlayerokAPI.types import AccountBalance
            return AccountBalance(id="", value=0, frozen=0, available=0, withdrawable=0, pending_income=0)
        except Exception as e:
            logger.error(f"Ошибка при получении баланса: {e}")
            logger.debug("TRACEBACK", exc_info=True)
            from PlayerokAPI.types import AccountBalance
            return AccountBalance(id="", value=0, frozen=0, available=0, withdrawable=0, pending_income=0)

    def update_lots_and_categories(self) -> bool:
        """Обновляет кэш лотов аккаунта для Telegram-ПУ и плагинов."""
        from Utils import playerok_tg_profile
        from locales.localizer import Localizer

        try:
            if not self.account.id:
                self.account.get()
            self.tg_profile = playerok_tg_profile.build_tg_profile(self.account)
            import datetime
            self.last_tg_profile_update = datetime.datetime.now()
            language = self.MAIN_CFG.get("Other", {}).get("language", "ru")
            _ = Localizer(language).translate
            logger.info(
                _("crd_tg_profile_updated", len(self.tg_profile.get_lots()), len(self.tg_profile.get_sorted_lots(2)))
            )
            return True
        except Exception as e:
            logger.error(f"Ошибка обновления лотов: {e}")
            logger.debug("TRACEBACK", exc_info=True)
            return False

    def __init_account(self):
        """Инициализирует аккаунт"""
        from locales.localizer import Localizer
        language = self.MAIN_CFG.get("Other", {}).get("language", "ru")
        localizer = Localizer(language)
        _ = localizer.translate
        
        while True:
            try:
                profile = self.account.get()
                self.balance = self.get_balance()
                greeting_text = cardinal_tools.create_greeting_text(self)
                cardinal_tools.set_console_title(f"Playerok Cardinal - {profile.username} ({profile.id})")
                for line in greeting_text.split("\n"):
                    logger.info(line)
                break
            except TimeoutError:
                logger.error(_("crd_acc_get_timeout_err"))
            except Exception as e:
                logger.error(f"Ошибка при авторизации: {e}")
                logger.debug("TRACEBACK", exc_info=True)
            logger.warning(_("crd_try_again_in_n_secs", 2))
            time.sleep(2)

    def __init_telegram(self):
        """Инициализирует Telegram бота"""
        if self.MAIN_CFG["Telegram"].get("enabled") == "1":
            from tg_bot import bot
            self.telegram = bot.TGBot(self)
            self.telegram.init()
            Thread(target=self.telegram.run, daemon=True).start()

    def init(self):
        from locales.localizer import Localizer
        language = self.MAIN_CFG.get("Other", {}).get("language", "ru")
        localizer = Localizer(language)
        _ = localizer.translate
        
        
        handlers.register_handlers(self)
        
        if self.MAIN_CFG["Telegram"].get("enabled") == "1":
            self.__init_telegram()
            try:
                from tg_bot import auto_response_cp, auto_delivery_cp, config_loader_cp, templates_cp, plugins_cp, \
                                   file_uploader, authorized_users_cp, proxy_cp, default_cp
                for module in [auto_response_cp, auto_delivery_cp, config_loader_cp, templates_cp, plugins_cp,
                               file_uploader, authorized_users_cp, proxy_cp, default_cp]:
                    try:
                        self.add_handlers_from_plugin(module)
                    except Exception as e:
                        logger.error(f"Ошибка при регистрации обработчиков модуля {module.__name__}: {e}")
                        logger.debug("TRACEBACK", exc_info=True)
                
                self.run_handlers(self.pre_init_handlers, (self,))
            except Exception as e:
                logger.warning(f"Ошибка при загрузке Telegram модулей: {e}")
                logger.debug("TRACEBACK", exc_info=True)
        
        self.__init_account()
        self.listener = EventListener(self.account)
        
        self.load_plugins()
        self.add_handlers()
        
        if self.telegram:
            self.run_handlers(self.pre_init_handlers, (self,))
        
        
        import time
        time.sleep(2)  # Даем время боту отправить сообщение bot_started и заполнить init_messages
        self.run_handlers(self.post_init_handlers, (self,))
        
        if self.telegram:
            self.telegram.update_commands_menu()
        
        return self
    
    def run_handlers(self, handlers_list: list, args: tuple):
        """
        Вызывает список обработчиков с указанными аргументами
        
        :param handlers_list: список обработчиков для вызова
        :param args: аргументы для передачи обработчикам
        """
        for handler in handlers_list:
            try:
                plugin_uuid = getattr(handler, "plugin_uuid", None)
                handler_name = getattr(handler, "__name__", str(handler))
                if plugin_uuid is None or (plugin_uuid in self.plugins and self.plugins[plugin_uuid].enabled):
                    handler(*args)
            except Exception as e:
                logger.error(f"Ошибка в обработчике {handler_name}: {e}")
                logger.debug("TRACEBACK", exc_info=True)

    def process_events(self):
        """Обрабатывает события от EventListener"""
        instance_id = self.run_id
        events_handlers = {
            PlayerokAPI.enums.EventTypes.CHAT_INITIALIZED: self.chat_initialized_handlers,
            PlayerokAPI.enums.EventTypes.NEW_MESSAGE: self.new_message_handlers,
            PlayerokAPI.enums.EventTypes.NEW_DEAL: self.new_deal_handlers,
            PlayerokAPI.enums.EventTypes.NEW_REVIEW: self.new_review_handlers,
            PlayerokAPI.enums.EventTypes.ITEM_PAID: self.item_paid_handlers,
            PlayerokAPI.enums.EventTypes.ITEM_SENT: self.item_sent_handlers,
            PlayerokAPI.enums.EventTypes.DEAL_CONFIRMED: self.deal_confirmed_handlers,
            PlayerokAPI.enums.EventTypes.DEAL_ROLLED_BACK: self.deal_rolled_back_handlers,
            PlayerokAPI.enums.EventTypes.DEAL_HAS_PROBLEM: self.deal_has_problem_handlers,
            PlayerokAPI.enums.EventTypes.DEAL_PROBLEM_RESOLVED: self.deal_problem_resolved_handlers,
            PlayerokAPI.enums.EventTypes.DEAL_STATUS_CHANGED: self.deal_status_changed_handlers,
        }
        
        requests_delay = int(self.MAIN_CFG["Other"].get("requestsDelay", "4"))
        
        for event in self.listener.listen(requests_delay=requests_delay):
            if instance_id != self.run_id:
                break
            
            event_type = event.type
            logger.info(f"📨 Получено событие: {event_type}")
            if event_type in events_handlers:
                logger.info(f"📋 Обработка события {event_type}, обработчиков: {len(events_handlers[event_type])}")
                for handler in events_handlers[event_type]:
                    try:
                        handler_name = handler.__name__ if hasattr(handler, '__name__') else str(handler)
                        logger.info(f"🔧 Вызов обработчика: {handler_name}")
                        handler(self, event)
                    except Exception as e:
                        logger.error(f"Ошибка в обработчике события {event_type}: {e}")
                        logger.debug("TRACEBACK", exc_info=True)
            else:
                logger.debug(f"⚠️ Событие {event_type} не имеет обработчиков")

    def start_automation_threads(self):
        if self._automation_threads_started:
            return
        self._automation_threads_started = True
        from Utils import playerok_automation
        Thread(target=playerok_automation.bump_items_loop, args=(self,), daemon=True).start()
        Thread(target=playerok_automation.withdrawal_loop, args=(self,), daemon=True).start()
        Thread(target=playerok_automation.auto_disable_loop, args=(self,), daemon=True).start()
        logger.info("Фоновые потоки автоматизации запущены")

    def run(self):
        self.run_id += 1
        self.running = True
        self.start_time = int(time.time())
        self.start_automation_threads()

        try:
            self.process_events()
        except KeyboardInterrupt:
            self.running = False
        except Exception as e:
            logger.error(f"Ошибка при обработке событий: {e}")
            logger.debug("TRACEBACK", exc_info=True)
            self.running = False

    @property
    def block_tg_login(self) -> bool:
        return self.MAIN_CFG["Telegram"].get("blockLogin", "0") == "1"
    
    @property
    def old_mode_enabled(self) -> bool:
        """Возвращает, включен ли старый режим получения сообщений"""
        playerok_section = self.MAIN_CFG.get("Playerok", {})
        if isinstance(playerok_section, dict):
            return playerok_section.get("oldMsgGetMode", "0") == "1"
        return playerok_section.getboolean("oldMsgGetMode")
    
    @property
    def keep_sent_messages_unread(self) -> bool:
        """Возвращает, нужно ли оставлять сообщения непрочитанными при отправке"""
        playerok_section = self.MAIN_CFG.get("Playerok", {})
        if isinstance(playerok_section, dict):
            return playerok_section.get("keepSentMessagesUnread", "0") == "1"
        return playerok_section.getboolean("keepSentMessagesUnread")
    
    def switch_msg_get_mode(self):
        """Переключает режим получения сообщений"""
        playerok_section = self.MAIN_CFG.get("Playerok", {})
        if isinstance(playerok_section, dict):
            current_value = playerok_section.get("oldMsgGetMode", "0")
            new_value = "1" if current_value == "0" else "0"
            playerok_section["oldMsgGetMode"] = new_value
        else:
            current_value = "1" if playerok_section.getboolean("oldMsgGetMode") else "0"
            new_value = "0" if current_value == "1" else "1"
            playerok_section["oldMsgGetMode"] = new_value
        
        self.save_config(self.MAIN_CFG, "configs/_main.cfg")
    
    @staticmethod
    def save_config(config: dict | ConfigParser, path: str):
        """Сохраняет конфиг в файл"""
        import configparser
        if isinstance(config, dict):
            cfg = configparser.ConfigParser(delimiters=(":",), interpolation=None)
            cfg.optionxform = str
            for section_name, section_data in config.items():
                cfg.add_section(section_name)
                for key, value in section_data.items():
                    cfg.set(section_name, key, str(value))
            with open(path, "w", encoding="utf-8") as f:
                cfg.write(f)
        else:
            with open(path, "w", encoding="utf-8") as f:
                config.write(f)

    def send_message(self, chat_id: str | int, text: str, chat_name: str = "", watermark: bool = True):
        """
        Отправляет сообщение в чат
        
        :param chat_id: ID чата
        :param text: текст сообщения
        :param chat_name: название чата (необязательно)
        :param watermark: добавлять ли водяной знак в начало сообщения? (по умолчанию True)
        """
        try:
            chat_id_str = str(chat_id)
            if watermark and self.MAIN_CFG.get("Other", {}).get("watermark") and not text.strip().startswith("$photo="):
                watermark_text = self.MAIN_CFG.get("Other", {}).get("watermark", "")
                if watermark_text:
                    text = f"{watermark_text}\n{text}"
            
            keep_unread = self.keep_sent_messages_unread
            mark_chat_as_read = not keep_unread
            
            self.account.send_message(chat_id_str, text, mark_chat_as_read=mark_chat_as_read)
            return True
        except Exception as e:
            logger.error(f"Ошибка при отправке сообщения: {e}")
            logger.debug("TRACEBACK", exc_info=True)
            return False
    
    @staticmethod
    def is_plugin(file: str) -> bool:
        """
        Есть ли "noplug" в начале файла плагина?

        :param file: файл плагина.
        """
        with open(f"plugins/{file}", "r", encoding="utf-8") as f:
            line = f.readline()
        if line.startswith("#"):
            line = line.replace("\n", "")
            args = line.split()
            if "noplug" in args:
                return False
        return True

    @staticmethod
    def load_plugin(from_file: str) -> tuple:
        """
        Создает модуль из переданного файла-плагина и получает необходимые поля для PluginData.
        :param from_file: путь до файла-плагина.

        :return: плагин, поля плагина.
        """
        spec = importlib.util.spec_from_file_location(f"plugins.{from_file[:-3]}", f"plugins/{from_file}")
        plugin = importlib.util.module_from_spec(spec)
        sys.modules[f"plugins.{from_file[:-3]}"] = plugin
        spec.loader.exec_module(plugin)

        fields = ["NAME", "VERSION", "DESCRIPTION", "CREDITS", "SETTINGS_PAGE", "UUID", "BIND_TO_DELETE"]
        result = {}

        for i in fields:
            try:
                value = getattr(plugin, i)
            except AttributeError:
                import Utils.exceptions
                raise Utils.exceptions.FieldNotExistsError(i, from_file)
            result[i] = value
        return plugin, result

    @staticmethod
    def is_uuid_valid(uuid: str) -> bool:
        """
        Проверяет, валиден ли UUID.

        :param uuid: UUID для проверки.

        :return: True, если UUID валиден, иначе - False.
        """
        try:
            UUID(uuid)
            return True
        except:
            return False

    def load_plugins(self):
        """
        Импортирует все плагины из папки plugins.
        """
        from locales.localizer import Localizer
        language = self.MAIN_CFG.get("Other", {}).get("language", "ru")
        localizer = Localizer(language)
        _ = localizer.translate
        
        if not os.path.exists("plugins"):
            logger.warning(_("crd_no_plugins_folder"))
            return
        plugins = [file for file in os.listdir("plugins") if file.endswith(".py") and file != "__init__.py"]
        if not plugins:
            logger.info(_("crd_no_plugins"))
            return

        sys.path.append("plugins")
        for file in plugins:
            try:
                if not self.is_plugin(file):
                    continue
                plugin, data = self.load_plugin(file)
            except Exception as e:
                logger.error(_("crd_plugin_load_err", file))
                logger.debug("TRACEBACK", exc_info=True)
                continue

            if not self.is_uuid_valid(data["UUID"]):
                logger.error(_("crd_invalid_uuid", file))
                continue

            if data["UUID"] in self.plugins:
                logger.error(_("crd_uuid_already_registered", data['UUID'], data['NAME']))
                continue

            plugin_data = PluginData(
                data["NAME"], data["VERSION"], data["DESCRIPTION"], data["CREDITS"], data["UUID"],
                f"plugins/{file}", plugin, data["SETTINGS_PAGE"], data["BIND_TO_DELETE"],
                False if data["UUID"] in self.disabled_plugins else True,
                True if data["UUID"] in self.pinned_plugins else False,
            )

            self.plugins[data["UUID"]] = plugin_data

    def add_handlers_from_plugin(self, plugin, uuid: str | None = None):
        """
        Добавляет хэндлеры из плагина + присваивает каждому хэндлеру UUID плагина.

        :param plugin: модуль (плагин).
        :param uuid: UUID плагина (None для встроенных хэндлеров).
        """
        plugin_name = getattr(plugin, "__name__", str(plugin))
        handlers_count = 0
        for name in self.handler_bind_var_names:
            try:
                functions = getattr(plugin, name)
                if functions:
                    for func in functions:
                        func.plugin_uuid = uuid
                    self.handler_bind_var_names[name].extend(functions)
                    handlers_count += len(functions)
            except AttributeError:
                continue
        from locales.localizer import Localizer
        language = self.MAIN_CFG.get("Other", {}).get("language", "ru")
        localizer = Localizer(language)
        _ = localizer.translate
        if handlers_count > 0:
            logger.info(_("crd_handlers_registered", plugin.__name__) + f" ({handlers_count} обработчиков)")
    def add_handlers(self):
        """
        Регистрирует хэндлеры из всех плагинов.
        """
        for i in self.plugins:
            plugin = self.plugins[i].plugin
            self.add_handlers_from_plugin(plugin, i)

    def toggle_plugin(self, uuid):
        """
        Активирует / деактивирует плагин.
        :param uuid: UUID плагина.
        """
        self.plugins[uuid].enabled = not self.plugins[uuid].enabled
        if self.plugins[uuid].enabled and uuid in self.disabled_plugins:
            self.disabled_plugins.remove(uuid)
        elif not self.plugins[uuid].enabled and uuid not in self.disabled_plugins:
            self.disabled_plugins.append(uuid)
        cardinal_tools.cache_disabled_plugins(self.disabled_plugins)

    def pin_plugin(self, uuid: str):
        self.plugins[uuid].pinned = not self.plugins[uuid].pinned
        if not self.plugins[uuid].pinned and uuid in self.pinned_plugins:
            self.pinned_plugins.remove(uuid)
        elif self.plugins[uuid].pinned and uuid not in self.pinned_plugins:
            self.pinned_plugins.append(uuid)
        cardinal_tools.cache_pinned_plugins(self.pinned_plugins)

    def reload_automation_cfg(self):
        self.auto_bump_cfg = cardinal_tools.load_json_config(
            "configs/auto_bump.json", cardinal_tools.DEFAULT_AUTO_BUMP
        )
        self.auto_complete_cfg = cardinal_tools.load_json_config(
            "configs/auto_complete.json", cardinal_tools.DEFAULT_AUTO_COMPLETE
        )
        self.auto_withdrawal_cfg = cardinal_tools.load_json_config(
            "configs/auto_withdrawal.json", cardinal_tools.DEFAULT_AUTO_WITHDRAWAL
        )

    def add_telegram_commands(self, uuid: str, commands: list[tuple[str, str, bool]]):
        """
        Добавляет команды в список команд плагина.
        [
            ("команда1", "описание команды", Добавлять ли в меню команд (True / False)),
            ("команда2", "описание команды", Добавлять ли в меню команд (True / False))
        ]

        :param uuid: UUID плагина.
        :param commands: список команд (без "/")
        """
        if uuid not in self.plugins:
            return

        for i in commands:
            self.plugins[uuid].commands[i[0]] = i[1]
            if i[2] and self.telegram:
                self.telegram.add_command_to_menu(i[0], i[1])

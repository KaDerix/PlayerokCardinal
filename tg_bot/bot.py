"""
В данном модуле написан Telegram бот.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from PlayerokAPI import Account
from tg_bot.utils import NotificationTypes

if TYPE_CHECKING:
    from cardinal import Cardinal

import os
import sys
import time
import random
import string
import psutil
import telebot
from telebot.apihelper import ApiTelegramException
import logging

from telebot.types import InlineKeyboardMarkup as K, InlineKeyboardButton as B, Message, CallbackQuery, BotCommand
from tg_bot import utils, static_keyboards as skb, keyboards as kb, CBT
from Utils import cardinal_tools, updater
from locales.localizer import Localizer

logger = logging.getLogger("TGBot")
localizer = Localizer()
_ = localizer.translate
telebot.apihelper.ENABLE_MIDDLEWARE = True


class TGBot:
    def __init__(self, cardinal: Cardinal):
        self.cardinal = cardinal
        if cardinal.MAIN_CFG["Telegram"]["proxy"]:
            telebot.apihelper.proxy = {"https": cardinal.MAIN_CFG["Telegram"]["proxy"],
                                       "http": cardinal.MAIN_CFG["Telegram"]["proxy"]}
        self.bot = telebot.TeleBot(self.cardinal.MAIN_CFG["Telegram"]["token"], parse_mode="HTML",
                                   allow_sending_without_reply=True, num_threads=5)

        self.file_handlers = {}  # хэндлеры, привязанные к получению файла.
        self.attempts = {}  # {user_id: attempts} - попытки авторизации в Telegram ПУ.
        self.init_messages = []  # [(chat_id, message_id)] - список сообщений о запуске TG бота.

        # {
        #     chat_id: {
        #         user_id: {
        #             "state": "state",
        #             "data": { ... },
        #             "mid": int
        #         }
        #     }
        # }
        self.user_states = {}

        # {
        #    chat_id: {
        #        utils.NotificationTypes.new_message: bool,
        #        utils.NotificationTypes.new_order: bool,
        #        ...
        #    },
        # }
        #
        self.notification_settings = utils.load_notification_settings()  # настройки уведомлений.
        self.answer_templates = utils.load_answer_templates()  # заготовки ответов.
        self.authorized_users = utils.load_authorized_users()  # авторизированные пользователи.

        # Словарь для обработчиков команд (используется для маршрутизации)
        self.command_handlers = {
            "menu": "cmd_menu",
            "profile": "cmd_profile",
            "restart": "cmd_restart",
            "check_updates": "cmd_check_updates",
            "update": "cmd_update",
            "token": "cmd_token",
            "ban": "cmd_ban",
            "unban": "cmd_unban",
            "black_list": "cmd_black_list",
            "upload_chat_img": "cmd_upload_chat_img",
            "upload_offer_img": "cmd_upload_offer_img",
            "upload_plugin": "cmd_upload_plugin",
            "test_lot": "cmd_test_lot",
            "logs": "cmd_logs",
            "about": "cmd_about",
            "sys": "cmd_sys",
            "get_backup": "cmd_get_backup",
            "create_backup": "cmd_create_backup",
            "upload_backup": "cmd_upload_backup",
            "del_logs": "cmd_del_logs",
            "power_off": "cmd_power_off",
            "watermark": "cmd_watermark",
        }
        # Словарь для меню команд (используется для Bot API)
        # Ключи - это ключи локализации, которые будут переведены в setup_commands
        self.commands = {
            "menu": "cmd_menu",
            "profile": "cmd_profile",
            "restart": "cmd_restart",
            "check_updates": "cmd_check_updates",
            "update": "cmd_update",
            "token": "cmd_token",
            "ban": "cmd_ban",
            "unban": "cmd_unban",
            "black_list": "cmd_black_list",
            "upload_chat_img": "cmd_upload_chat_img",
            "upload_offer_img": "cmd_upload_offer_img",
            "upload_plugin": "cmd_upload_plugin",
            "test_lot": "cmd_test_lot",
            "logs": "cmd_logs",
            "about": "cmd_about",
            "sys": "cmd_sys",
            "get_backup": "cmd_get_backup",
            "create_backup": "cmd_create_backup",
            "upload_backup": "cmd_upload_backup",
            "del_logs": "cmd_del_logs",
            "power_off": "cmd_power_off",
            "watermark": "cmd_watermark",
        }
        self.__default_notification_settings = {
            utils.NotificationTypes.ad: 1,
            utils.NotificationTypes.announcement: 1
        }

    # User states
    def get_state(self, chat_id: int, user_id: int) -> dict | None:
        """
        Получает текущее состояние пользователя.

        :param chat_id: id чата.
        :param user_id: id пользователя.

        :return: данные состояния пользователя.
        """
        try:
            return self.user_states[chat_id][user_id]
        except KeyError:
            return None

    def set_state(self, chat_id: int, message_id: int, user_id: int, state: str, data: dict | None = None):
        """
        Устанавливает состояние для пользователя.

        :param chat_id: id чата.
        :param message_id: id сообщения, после которого устанавливается данное состояние.
        :param user_id: id пользователя.
        :param state: состояние.
        :param data: доп. данные.
        """
        if chat_id not in self.user_states:
            self.user_states[chat_id] = {}
        self.user_states[chat_id][user_id] = {"state": state, "mid": message_id, "data": data or {}}

    def clear_state(self, chat_id: int, user_id: int, del_msg: bool = False) -> int | None:
        """
        Очищает состояние пользователя.

        :param chat_id: id чата.
        :param user_id: id пользователя.
        :param del_msg: удалять ли сообщение, после которого было обозначено текущее состояние.

        :return: ID сообщения-инициатора или None, если состояние и так было пустое.
        """
        try:
            state = self.user_states[chat_id][user_id]
        except KeyError:
            return None

        msg_id = state.get("mid")
        del self.user_states[chat_id][user_id]
        if del_msg:
            try:
                self.bot.delete_message(chat_id, msg_id)
            except:
                pass
        return msg_id

    def check_state(self, chat_id: int, user_id: int, state: str) -> bool:
        """
        Проверяет, является ли состояние указанным.

        :param chat_id: id чата.
        :param user_id: id пользователя.
        :param state: состояние.

        :return: True / False
        """
        try:
            return self.user_states[chat_id][user_id]["state"] == state
        except KeyError:
            return False

    # Notification settings
    def is_notification_enabled(self, chat_id: int | str, notification_type: str) -> bool:
        """
        Включен ли указанный тип уведомлений в указанном чате?

        :param chat_id: ID Telegram чата.
        :param notification_type: тип уведомлений.
        """
        try:
            return bool(self.notification_settings[str(chat_id)][notification_type])
        except KeyError:
            return False

    def toggle_notification(self, chat_id: int, notification_type: str) -> bool:
        """
        Переключает указанный тип уведомлений в указанном чате и сохраняет настройки уведомлений.

        :param chat_id: ID Telegram чата.
        :param notification_type: тип уведомлений.

        :return: вкл / выкл указанный тип уведомлений в указанном чате.
        """
        chat_id = str(chat_id)
        if chat_id not in self.notification_settings:
            self.notification_settings[chat_id] = {}

        self.notification_settings[chat_id][notification_type] = not self.is_notification_enabled(chat_id,
                                                                                                  notification_type)
        utils.save_notification_settings(self.notification_settings)
        return self.notification_settings[chat_id][notification_type]

    # handler binders
    def is_file_handler(self, m: Message):
        return self.get_state(m.chat.id, m.from_user.id) and m.content_type in ["photo", "document"]

    def file_handler(self, state, handler):
        self.file_handlers[state] = handler

    def run_file_handlers(self, m: Message):
        if (state := self.get_state(m.chat.id, m.from_user.id)) is None \
                or state["state"] not in self.file_handlers:
            return
        try:
            self.file_handlers[state["state"]](m)
        except:
            logger.error(_("log_tg_handler_error"))
            logger.debug("TRACEBACK", exc_info=True)

    def msg_handler(self, handler, **kwargs):
        """
        Регистрирует хэндлер, срабатывающий при новом сообщении.

        :param handler: хэндлер.
        :param kwargs: аргументы для хэндлера.
        """
        bot_instance = self.bot

        @bot_instance.message_handler(**kwargs)
        def run_handler(message: Message):
            try:
                handler(message)
            except Exception as e:
                logger.error(_("log_tg_handler_error"))
                logger.debug("TRACEBACK", exc_info=True)
                try:
                    bot_instance.send_message(message.chat.id, "❌ Произошла ошибка. Попробуйте через пару секунд...")
                except:
                    pass

    def cbq_handler(self, handler, func, **kwargs):
        """
        Регистрирует хэндлер, срабатывающий при новом callback'е.

        :param handler: хэндлер.
        :param func: функция-фильтр.
        :param kwargs: аргументы для хэндлера.
        """
        bot_instance = self.bot
        handler_name = getattr(handler, "__name__", str(handler))
        logger.debug(f"Регистрация callback handler: {handler_name}")

        @bot_instance.callback_query_handler(func, **kwargs)
        def run_handler(call: CallbackQuery):
            try:
                logger.debug(f"Callback получен: {call.data}, обработчик: {handler_name}")
                handler(call)
                logger.debug(f"Callback обработан успешно: {call.data}")
            except Exception as e:
                logger.error(_("log_tg_handler_error") + f" (handler: {handler_name}, data: {call.data})")
                logger.debug("TRACEBACK", exc_info=True)

    def mdw_handler(self, handler, **kwargs):
        """
        Регистрирует промежуточный хэндлер.

        :param handler: хэндлер.
        :param kwargs: аргументы для хэндлера.
        """
        bot_instance = self.bot

        @bot_instance.middleware_handler(**kwargs)
        def run_handler(bot, update):
            try:
                handler(bot, update)
            except Exception as e:
                logger.error(_("log_tg_handler_error"))
                logger.debug("TRACEBACK", exc_info=True)

    # Система свой-чужой 0_0
    def setup_chat_notifications(self, bot: TGBot, m: Message):
        """
        Устанавливает настройки уведомлений по умолчанию в новом чате.
        """
        if str(m.chat.id) in self.notification_settings and m.from_user.id in self.authorized_users and \
                self.is_notification_enabled(m.chat.id, NotificationTypes.critical):
            return
        elif str(m.chat.id) in self.notification_settings and m.from_user.id in self.authorized_users and not \
                self.is_notification_enabled(m.chat.id, NotificationTypes.critical):
            self.notification_settings[str(m.chat.id)][NotificationTypes.critical] = 1
            utils.save_notification_settings(self.notification_settings)
            return
        elif str(m.chat.id) not in self.notification_settings:
            self.notification_settings[str(m.chat.id)] = self.__default_notification_settings.copy()
            utils.save_notification_settings(self.notification_settings)

    def reg_admin(self, m: Message):
        """
        Проверяет, есть ли пользователь в списке пользователей с доступом к ПУ TG.
        """
        lang = m.from_user.language_code
        if m.chat.type != "private" or (self.attempts.get(m.from_user.id, 0) >= 5) or m.text is None:
            return
        if not self.cardinal.block_tg_login and \
                cardinal_tools.check_password(m.text, self.cardinal.MAIN_CFG["Telegram"]["secretKeyHash"]):
            self.send_notification(text=_("access_granted_notification", m.from_user.username, m.from_user.id),
                                   notification_type=NotificationTypes.critical, pin=True)
            self.authorized_users[m.from_user.id] = {}
            utils.save_authorized_users(self.authorized_users)
            if str(m.chat.id) not in self.notification_settings or not self.is_notification_enabled(m.chat.id,
                                                                                                    NotificationTypes.critical):
                self.notification_settings[str(m.chat.id)] = self.__default_notification_settings.copy()
                self.notification_settings[str(m.chat.id)][NotificationTypes.critical] = 1
                utils.save_notification_settings(self.notification_settings)
            text = _("access_granted", language=lang)
            kb_links = None
            logger.warning(_("log_access_granted", m.from_user.username, m.from_user.id))
        else:
            self.attempts[m.from_user.id] = self.attempts.get(m.from_user.id, 0) + 1
            text = _("access_denied", m.from_user.username, language=lang)
            kb_links = kb.LINKS_KB(language=lang)
            logger.warning(_("log_access_attempt", m.from_user.username, m.from_user.id))
        self.bot.send_message(m.chat.id, text, reply_markup=kb_links)

    def ignore_unauthorized_users(self, c: CallbackQuery):
        """
        Игнорирует callback'и от не авторизированных пользователей.
        """
        logger.warning(_("log_click_attempt", c.from_user.username, c.from_user.id, c.message.chat.username,
                         c.message.chat.id))
        self.attempts[c.from_user.id] = self.attempts.get(c.from_user.id, 0) + 1
        if self.attempts[c.from_user.id] <= 5:
            self.bot.answer_callback_query(c.id, _("adv_poc", language=c.from_user.language_code), show_alert=True)
        return

    # Команды
    def send_settings_menu(self, m: Message):
        """
        Отправляет основное меню настроек (новым сообщением).
        """
        if m.from_user.id not in self.authorized_users:
            self.reg_admin(m)
            return
        self.bot.send_message(m.chat.id, _("desc_main"), reply_markup=skb.SETTINGS_SECTIONS())

    def send_profile(self, m: Message):
        """
        Отправляет статистику аккаунта.
        """
        if m.from_user.id not in self.authorized_users:
            self.reg_admin(m)
            return
        self.bot.send_message(m.chat.id, utils.generate_profile_text(self.cardinal),
                              reply_markup=skb.REFRESH_BTN())

    def act_change_cookie(self, m: Message):
        """
        Активирует режим ввода token.
        """
        if m.from_user.id not in self.authorized_users:
            self.reg_admin(m)
            return
        result = self.bot.send_message(m.chat.id, _("act_change_token"), reply_markup=skb.CLEAR_STATE_BTN())
        self.set_state(m.chat.id, result.id, m.from_user.id, CBT.CHANGE_GOLDEN_KEY)

    def change_cookie(self, m: Message):
        """
        Меняет token аккаунта Playerok.
        """
        self.clear_state(m.chat.id, m.from_user.id, True)
        token = m.text.strip()
        if not token or len(token.split()) != 1:
            self.bot.send_message(m.chat.id, _("token_incorrect_format"))
            return
        self.bot.delete_message(m.chat.id, m.id)
        acc = self.cardinal.account
        new_account = Account(
            token,
            ddg5=acc.ddg5,
            cookies=dict(acc.cookies),
            user_agent=acc.user_agent,
            proxy=self.cardinal.proxy
        )
        try:
            new_account.get()
        except:
            logger.warning("Произошла ошибка")  # locale
            logger.debug("TRACEBACK", exc_info=True)
            self.bot.send_message(m.chat.id, _("token_error"))
            return

        one_acc = False
        if new_account.id == self.cardinal.account.id or self.cardinal.account.id is None:
            one_acc = True
            self.cardinal.account.token = token
            self.cardinal.account.cookies["token"] = token
            try:
                self.cardinal.account.get()
                self.cardinal.balance = self.cardinal.get_balance()
            except:
                logger.warning("Произошла ошибка")  # locale
                logger.debug("TRACEBACK", exc_info=True)
                self.bot.send_message(m.chat.id, _("token_error"))
                return
            accs = f" (<a href='https://playerok.com/users/{new_account.id}/'>{new_account.username}</a>)"
        else:
            accs = f" (<a href='https://playerok.com/users/{self.cardinal.account.id}/'>" \
                   f"{self.cardinal.account.username}</a> ➔ <a href='https://playerok.com/users/{new_account.id}/'>" \
                   f"{new_account.username}</a>)"

        if "Playerok" not in self.cardinal.MAIN_CFG:
            self.cardinal.MAIN_CFG["Playerok"] = {}
        self.cardinal.MAIN_CFG["Playerok"]["token"] = token
        self.cardinal.save_config(self.cardinal.MAIN_CFG, "configs/_main.cfg")
        self.bot.send_message(m.chat.id, f'{_("token_changed", accs)}{_("token_changed2") if not one_acc else ""}',
                              disable_web_page_preview=True)

    def update_profile(self, c: CallbackQuery):
        new_msg = self.bot.send_message(c.message.chat.id, _("updating_profile"))
        try:
            self.cardinal.account.get()
            self.cardinal.balance = self.cardinal.get_balance()
        except Exception as e:
            self.bot.edit_message_text(_("profile_updating_error"), new_msg.chat.id, new_msg.id)
            logger.debug("TRACEBACK", exc_info=True)
            self.bot.answer_callback_query(c.id)
            return

        self.bot.delete_message(new_msg.chat.id, new_msg.id)
        self.bot.edit_message_text(utils.generate_profile_text(self.cardinal), c.message.chat.id,
                                   c.message.id, reply_markup=skb.REFRESH_BTN())

    def act_manual_delivery_test(self, m: Message):
        """
        Активирует режим ввода названия лота для ручной генерации ключа теста автовыдачи.
        """
        if m.from_user.id not in self.authorized_users:
            self.reg_admin(m)
            return
        result = self.bot.send_message(m.chat.id, _("create_test_ad_key"), reply_markup=skb.CLEAR_STATE_BTN())
        self.set_state(m.chat.id, result.id, m.from_user.id, CBT.MANUAL_AD_TEST)

    def manual_delivery_text(self, m: Message):
        """
        Генерирует ключ теста автовыдачи (ручной режим).
        """
        self.clear_state(m.chat.id, m.from_user.id, True)
        lot_name = m.text.strip()
        key = "".join(random.sample(string.ascii_letters + string.digits, 50))
        self.cardinal.delivery_tests[key] = lot_name

        logger.info(_("log_new_ad_key", m.from_user.username, m.from_user.id, lot_name, key))
        self.bot.send_message(m.chat.id, _("test_ad_key_created", utils.escape(lot_name), key))

    def act_ban(self, m: Message):
        """
        Активирует режим ввода никнейма пользователя, которого нужно добавить в ЧС.
        """
        if m.from_user.id not in self.authorized_users:
            self.reg_admin(m)
            return
        result = self.bot.send_message(m.chat.id, _("act_blacklist"), reply_markup=skb.CLEAR_STATE_BTN())
        self.set_state(m.chat.id, result.id, m.from_user.id, CBT.BAN)

    def ban(self, m: Message):
        """
        Добавляет пользователя в ЧС.
        """
        self.clear_state(m.chat.id, m.from_user.id, True)
        nickname = m.text.strip()

        if nickname in self.cardinal.blacklist:
            self.bot.send_message(m.chat.id, _("already_blacklisted", nickname))
            return

        self.cardinal.blacklist.append(nickname)
        cardinal_tools.cache_blacklist(self.cardinal.blacklist)
        logger.info(_("log_user_blacklisted", m.from_user.username, m.from_user.id, nickname))
        self.bot.send_message(m.chat.id, _("user_blacklisted", nickname))

    def act_unban(self, m: Message):
        """
        Активирует режим ввода никнейма пользователя, которого нужно удалить из ЧС.
        """
        if m.from_user.id not in self.authorized_users:
            self.reg_admin(m)
            return
        result = self.bot.send_message(m.chat.id, _("act_unban"), reply_markup=skb.CLEAR_STATE_BTN())
        self.set_state(m.chat.id, result.id, m.from_user.id, CBT.UNBAN)

    def unban(self, m: Message):
        """
        Удаляет пользователя из ЧС.
        """
        self.clear_state(m.chat.id, m.from_user.id, True)
        nickname = m.text.strip()
        if nickname not in self.cardinal.blacklist:
            self.bot.send_message(m.chat.id, _("not_blacklisted", nickname))
            return
        self.cardinal.blacklist.remove(nickname)
        cardinal_tools.cache_blacklist(self.cardinal.blacklist)
        logger.info(_("log_user_unbanned", m.from_user.username, m.from_user.id, nickname))
        self.bot.send_message(m.chat.id, _("user_unbanned", nickname))

    def send_ban_list(self, m: Message):
        """
        Отправляет ЧС.
        """
        if m.from_user.id not in self.authorized_users:
            self.reg_admin(m)
            return
        if not self.cardinal.blacklist:
            self.bot.send_message(m.chat.id, _("blacklist_empty"))
            return
        blacklist = ", ".join(f"<code>{i}</code>" for i in sorted(self.cardinal.blacklist, key=lambda x: x.lower()))
        self.bot.send_message(m.chat.id, blacklist)

    def act_edit_watermark(self, m: Message):
        """
        Активирует режим ввода вотемарки сообщений.
        """
        if m.from_user.id not in self.authorized_users:
            self.reg_admin(m)
            return
        watermark = self.cardinal.MAIN_CFG["Other"]["watermark"]
        watermark = f"\n<code>{utils.escape(watermark)}</code>" if watermark else ""
        result = self.bot.send_message(m.chat.id, _("act_edit_watermark").format(watermark),
                                       reply_markup=skb.CLEAR_STATE_BTN())
        self.set_state(m.chat.id, result.id, m.from_user.id, CBT.EDIT_WATERMARK)

    def edit_watermark(self, m: Message):
        self.clear_state(m.chat.id, m.from_user.id, True)
        watermark = m.text if m.text != "-" else ""
        if re.fullmatch(r"\[[a-zA-Z]+]", watermark):
            self.bot.reply_to(m, _("watermark_error"))
            return

        preview = f"<a href=\"https://sfunpay.com/s/chat/zb/wl/zbwl4vwc8cc1wsftqnx5.jpg\">⁢</a>" if not \
            utils.has_brand_mark(watermark) else \
            f"<a href=\"https://sfunpay.com/s/chat/kd/8i/kd8isyquw660kcueck3g.jpg\">⁢</a>"
        if "Other" not in self.cardinal.MAIN_CFG:
            self.cardinal.MAIN_CFG["Other"] = {}
        self.cardinal.MAIN_CFG["Other"]["watermark"] = watermark
        self.cardinal.save_config(self.cardinal.MAIN_CFG, "configs/_main.cfg")
        if watermark:
            logger.info(_("log_watermark_changed", m.from_user.username, m.from_user.id, watermark))
            self.bot.reply_to(m, preview + _("watermark_changed", watermark))
        else:
            logger.info(_("log_watermark_deleted", m.from_user.username, m.from_user.id))
            self.bot.reply_to(m, preview + _("watermark_deleted"))

    def send_logs(self, m: Message):
        """
        Отправляет файл логов.
        """
        if m.from_user.id not in self.authorized_users:
            self.reg_admin(m)
            return
        if not os.path.exists("logs/log.log"):
            self.bot.send_message(m.chat.id, _("logfile_not_found"))
        else:
            self.bot.send_message(m.chat.id, _("logfile_sending"))
            try:
                with open("logs/log.log", "rb") as f:
                    log_bytes = f.read()
                from datetime import datetime
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                caption = (
                    _("gs_old_msg_mode").replace("{} ", "")
                    if hasattr(self.cardinal, "old_mode_enabled") and self.cardinal.old_mode_enabled
                    else ""
                )
                utils.send_document_named(
                    self.bot,
                    m.chat.id,
                    log_bytes,
                    f"PlayerokCardinal_log_{timestamp}.log",
                    caption=caption,
                )
                file_content = log_bytes.decode("utf-8", errors="ignore")
                if "TRACEBACK" in file_content:
                    file_content, right = file_content.rsplit("TRACEBACK", 1)
                    file_content = "\n[".join(file_content.rsplit("\n[", 2)[-2:])
                    right = right.split("\n[", 1)[0]  # locale
                    result = f"<b>Текст последней ошибки:</b>\n\n[{utils.escape(file_content)}TRACEBACK{utils.escape(right)}"
                    while result:
                        text, result = result[:4096], result[4096:]
                        self.bot.send_message(m.chat.id, text)
                        time.sleep(0.5)
                else:
                    self.bot.send_message(m.chat.id, "<b>Ошибок в последнем лог-файле не обнаружено.</b>")  # locale
            except Exception as e:
                logger.error(f"Ошибка отправки лог-файла: {e}")
                logger.debug("TRACEBACK", exc_info=True)
                self.bot.send_message(m.chat.id, _("logfile_error"))

    def del_logs(self, m: Message):
        """
        Удаляет ротированные лог-файлы (log.log.1, …) и очищает текущий logs/log.log.
        """
        if m.from_user.id not in self.authorized_users:
            self.reg_admin(m)
            return
        logs_dir = "logs"
        if not os.path.isdir(logs_dir):
            self.bot.send_message(m.chat.id, _("logfile_not_found"))
            return
        logger.info(
            f"[IMPORTANT] Удаляю логи по запросу пользователя $MAGENTA@{m.from_user.username} (id: {m.from_user.id})$RESET.")
        deleted = 0
        main_log = os.path.join(logs_dir, "log.log")
        for name in os.listdir(logs_dir):
            if not name.startswith("log.log.") or name == "log.log":
                continue
            path = os.path.join(logs_dir, name)
            if not os.path.isfile(path):
                continue
            try:
                os.remove(path)
                deleted += 1
            except OSError:
                logger.debug("TRACEBACK", exc_info=True)
        if os.path.isfile(main_log):
            try:
                with open(main_log, "w", encoding="utf-8"):
                    pass
                deleted += 1
            except OSError:
                logger.error("Не удалось очистить logs/log.log")
                logger.debug("TRACEBACK", exc_info=True)
                self.bot.send_message(m.chat.id, _("logfile_error"))
                return
        self.bot.send_message(m.chat.id, _("logfile_deleted").format(deleted))

    def about(self, m: Message):
        """
        Отправляет информацию о текущей версии бота.
        """
        if m.from_user.id not in self.authorized_users:
            self.reg_admin(m)
            return
        self.bot.send_message(m.chat.id, _("about", self.cardinal.VERSION))

    def check_updates(self, m: Message):
        if m.from_user.id not in self.authorized_users:
            self.reg_admin(m)
            return
        
        logger.info(f"Пользователь @{m.from_user.username} (ID: {m.from_user.id}) проверяет обновления.")
        curr_tag = f"v{self.cardinal.VERSION}"
        releases = updater.get_new_releases(curr_tag)
        if isinstance(releases, int):
            errors = {
                1: ["update_no_tags", ()],
                2: ["update_lasted", (curr_tag,)],
                3: ["update_get_error", ()],
            }
            self.bot.send_message(m.chat.id, _(errors[releases][0], *errors[releases][1]))
            return
        for release in releases:
            self.bot.send_message(m.chat.id, _("update_available", release.name, release.description))
            time.sleep(1)
        self.bot.send_message(m.chat.id, _("update_update"))

    def get_backup(self, m: Message):
        if m.from_user.id not in self.authorized_users:
            self.reg_admin(m)
            return
        logger.info(
            f"[IMPORTANT] Получаю бэкап по запросу пользователя $MAGENTA@{m.from_user.username} (id: {m.from_user.id})$RESET.")
        if os.path.exists("backup.zip"):  # locale
            with open(file_path := "backup.zip", 'rb') as file:
                modification_time = os.path.getmtime(file_path)
                formatted_time = time.strftime('%d.%m.%Y %H:%M:%S', time.localtime(modification_time))
                utils.send_document_named(
                    self.bot, m.chat.id, file, "backup.zip",
                    caption=f'{_("update_backup")}\n\n{formatted_time}',
                )
        else:
            self.bot.send_message(m.chat.id, _("update_backup_not_found"))

    def create_backup(self, m: Message):
        if m.from_user.id not in self.authorized_users:
            self.reg_admin(m)
            return
        if updater.create_backup():
            self.bot.send_message(m.chat.id, _("update_backup_error"))
            return False
        self.get_backup(m)
        return True

    def update(self, m: Message):
        if m.from_user.id not in self.authorized_users:
            self.reg_admin(m)
            return
        
        logger.info(f"Пользователь @{m.from_user.username} (ID: {m.from_user.id}) запустил обновление.")
        curr_tag = f"v{self.cardinal.VERSION}"
        releases = updater.get_new_releases(curr_tag)
        if isinstance(releases, int):
            errors = {
                1: ["update_no_tags", ()],
                2: ["update_lasted", (curr_tag,)],
                3: ["update_get_error", ()],
            }
            self.bot.send_message(m.chat.id, _(errors[releases][0], *errors[releases][1]))
            return
        if not self.create_backup(m):
            return
        release = releases[-1]
        if updater.download_zip(release.sources_link) \
                or (release_folder := updater.extract_update_archive()) == 1:
            self.bot.send_message(m.chat.id, _("update_download_error"))
            return
        self.bot.send_message(m.chat.id, _("update_downloaded").format(release.name, str(len(releases) - 1)))

        if updater.install_release(release_folder):
            self.bot.send_message(m.chat.id, _("update_install_error"))
            return

        if getattr(sys, 'frozen', False):
            self.bot.send_message(m.chat.id, _("update_done_exe"))
        else:
            self.bot.send_message(m.chat.id, _("update_done"))

    def send_system_info(self, m: Message):
        """
        Отправляет информацию о нагрузке на систему.
        """
        if m.from_user.id not in self.authorized_users:
            self.reg_admin(m)
            return
        current_time = int(time.time())
        uptime = current_time - self.cardinal.start_time

        ram = psutil.virtual_memory()
        cpu_usage = "\n".join(
            f"    CPU {i}:  <code>{l}%</code>" for i, l in enumerate(psutil.cpu_percent(percpu=True)))
        self.bot.send_message(m.chat.id, _("sys_info", cpu_usage, psutil.Process().cpu_percent(),
                                           ram.total // 1048576, ram.used // 1048576, ram.free // 1048576,
                                           psutil.Process().memory_info().rss // 1048576,
                                           cardinal_tools.time_to_str(uptime), m.chat.id))

    def restart_cardinal(self, m: Message):
        """
        Перезапускает кардинал.
        """
        if m.from_user.id not in self.authorized_users:
            self.reg_admin(m)
            return
        self.bot.send_message(m.chat.id, _("restarting"))
        cardinal_tools.restart_program()

    def ask_power_off(self, m: Message):
        """
        Просит подтверждение на отключение POC.
        """
        if m.from_user.id not in self.authorized_users:
            self.reg_admin(m)
            return
        self.bot.send_message(m.chat.id, _("power_off_0"), reply_markup=kb.power_off(self.cardinal.instance_id, 0))

    def cancel_power_off(self, c: CallbackQuery):
        """
        Отменяет выключение (удаляет клавиатуру с кнопками подтверждения).
        """
        self.bot.edit_message_text(_("power_off_cancelled"), c.message.chat.id, c.message.id)
        self.bot.answer_callback_query(c.id)

    def power_off(self, c: CallbackQuery):
        """
        Отключает POC.
        """
        split = c.data.split(":")
        state = int(split[1])
        instance_id = int(split[2])

        if instance_id != self.cardinal.instance_id:
            self.bot.edit_message_text(_("power_off_error"), c.message.chat.id, c.message.id)
            self.bot.answer_callback_query(c.id)
            return

        if state == 6:
            self.bot.edit_message_text(_("power_off_6"), c.message.chat.id, c.message.id)
            self.bot.answer_callback_query(c.id)
            cardinal_tools.shut_down()
            return

        self.bot.edit_message_text(_(f"power_off_{state}"), c.message.chat.id, c.message.id,
                                   reply_markup=kb.power_off(instance_id, state))
        self.bot.answer_callback_query(c.id)

    # Чат FunPay
    def act_send_funpay_message(self, c: CallbackQuery):
        """
        Активирует режим ввода сообщения для отправки его в чат Playerok.
        """
        split = c.data.split(":")
        # В PlayerokAPI node_id это UUID (строка), а не int
        node_id = str(split[1])
        # Получаем username из чата, так как его больше нет в callback_data
        try:
            chat = self.cardinal.account.get_chat(node_id)
            username = chat.users[0].username if chat.users and hasattr(chat.users[0], 'username') else str(chat.users[0].id) if chat.users else ""
        except Exception as e:
            logger.error(f"Ошибка получения чата {node_id}: {e}")
            username = ""
        result = self.bot.send_message(c.message.chat.id, _("enter_msg_text"), reply_markup=skb.CLEAR_STATE_BTN())
        self.set_state(c.message.chat.id, result.id, c.from_user.id,
                       CBT.SEND_FP_MESSAGE, {"node_id": node_id, "username": username})
        self.bot.answer_callback_query(c.id)

    def send_funpay_message(self, message: Message):
        """
        Отправляет сообщение в чат Playerok.
        """
        data = self.get_state(message.chat.id, message.from_user.id)["data"]
        node_id, username = data["node_id"], data["username"]
        self.clear_state(message.chat.id, message.from_user.id, True)
        response_text = message.text.strip()
        # В PlayerokAPI node_id это UUID (строка)
        result = self.cardinal.send_message(str(node_id), response_text, username)
        if result:
            # Создаем клавиатуру вручную, так как reply ожидает int, а у нас UUID
            from telebot.types import InlineKeyboardMarkup as K, InlineKeyboardButton as B
            keyboard = K()
            keyboard.row(
                B(_("msg_reply2"), None, f"{CBT.SEND_FP_MESSAGE}:{node_id}"),
                B(_("msg_templates"), None, f"{CBT.TMPLT_LIST_ANS_MODE}:0:{node_id}:1:1")
            )
            keyboard.row(B(_("msg_more"), None, f"{CBT.EXTEND_CHAT}:{node_id}"))
            keyboard.row(B(f"🌐 {username}", url=f"https://playerok.com/chats/{node_id}"))
            self.bot.reply_to(message, _("msg_sent", node_id, username), reply_markup=keyboard)
        else:
            keyboard = K()
            keyboard.row(
                B(_("msg_reply"), None, f"{CBT.SEND_FP_MESSAGE}:{node_id}"),
                B(_("msg_templates"), None, f"{CBT.TMPLT_LIST_ANS_MODE}:0:{node_id}:0:0")
            )
            keyboard.row(B(f"🌐 {username}", url=f"https://playerok.com/chats/{node_id}"))
            self.bot.reply_to(message, _("msg_sending_error", node_id, username), reply_markup=keyboard)

    def act_upload_image(self, m: Message):
        """
        Активирует режим ожидания изображения для последующей выгрузки на Playerok.
        """
        if m.from_user.id not in self.authorized_users:
            self.reg_admin(m)
            return
        cbt = CBT.UPLOAD_CHAT_IMAGE if m.text.startswith("/upload_chat_img") else CBT.UPLOAD_OFFER_IMAGE
        result = self.bot.send_message(m.chat.id, _("send_img"), reply_markup=skb.CLEAR_STATE_BTN())
        self.set_state(m.chat.id, result.id, m.from_user.id, cbt)

    def act_upload_backup(self, m: Message):
        """
        Активирует режим ожидания бекапа.
        """
        if m.from_user.id not in self.authorized_users:
            self.reg_admin(m)
            return
        result = self.bot.send_message(m.chat.id, _("send_backup"), reply_markup=skb.CLEAR_STATE_BTN())
        self.set_state(m.chat.id, result.id, m.from_user.id, CBT.UPLOAD_BACKUP)

    def act_edit_greetings_text(self, c: CallbackQuery):
        variables = ["v_date", "v_date_text", "v_full_date_text", "v_time", "v_full_time", "v_username",
                     "v_message_text", "v_chat_id", "v_chat_name", "v_photo", "v_sleep"]
        text = f"{_('v_edit_greeting_text')}\n\n{_('v_list')}:\n" + "\n".join(_(i) for i in variables)
        result = self.bot.send_message(c.message.chat.id, text, reply_markup=skb.CLEAR_STATE_BTN())
        self.set_state(c.message.chat.id, result.id, c.from_user.id, CBT.EDIT_GREETINGS_TEXT)
        self.bot.answer_callback_query(c.id)

    def edit_greetings_text(self, m: Message):
        self.clear_state(m.chat.id, m.from_user.id, True)
        if "Greetings" not in self.cardinal.MAIN_CFG:
            self.cardinal.MAIN_CFG["Greetings"] = {}
        self.cardinal.MAIN_CFG["Greetings"]["greetingsText"] = m.text
        logger.info(_("log_greeting_changed", m.from_user.username, m.from_user.id, m.text))
        self.cardinal.save_config(self.cardinal.MAIN_CFG, "configs/_main.cfg")
        keyboard = K() \
            .row(B(_("gl_back"), callback_data=f"{CBT.CATEGORY}:gr"),
                 B(_("gl_edit"), callback_data=CBT.EDIT_GREETINGS_TEXT))
        self.bot.reply_to(m, _("greeting_changed"), reply_markup=keyboard)

    def act_edit_greetings_cooldown(self, c: CallbackQuery):
        text = _('v_edit_greeting_cooldown')
        result = self.bot.send_message(c.message.chat.id, text, reply_markup=skb.CLEAR_STATE_BTN())
        self.set_state(c.message.chat.id, result.id, c.from_user.id, CBT.EDIT_GREETINGS_COOLDOWN)
        self.bot.answer_callback_query(c.id)

    def edit_greetings_cooldown(self, m: Message):
        self.clear_state(m.chat.id, m.from_user.id, True)
        try:
            cooldown = float(m.text)
        except:
            self.bot.reply_to(m, _("gl_error_try_again"))
            return
        if "Greetings" not in self.cardinal.MAIN_CFG:
            self.cardinal.MAIN_CFG["Greetings"] = {}
        self.cardinal.MAIN_CFG["Greetings"]["greetingsCooldown"] = str(cooldown)
        logger.info(_("log_greeting_cooldown_changed", m.from_user.username, m.from_user.id, m.text))
        self.cardinal.save_config(self.cardinal.MAIN_CFG, "configs/_main.cfg")
        keyboard = K() \
            .row(B(_("gl_back"), callback_data=f"{CBT.CATEGORY}:gr"),
                 B(_("gl_edit"), callback_data=CBT.EDIT_GREETINGS_COOLDOWN))
        self.bot.reply_to(m, _("greeting_cooldown_changed").format(m.text), reply_markup=keyboard)

    def act_edit_order_confirm_reply_text(self, c: CallbackQuery):
        variables = ["v_date", "v_date_text", "v_full_date_text", "v_time", "v_full_time", "v_username",
                     "v_order_id", "v_order_link", "v_order_title", "v_game", "v_category", "v_category_fullname",
                     "v_photo", "v_sleep"]
        text = f"{_('v_edit_order_confirm_text')}\n\n{_('v_list')}:\n" + "\n".join(_(i) for i in variables)
        result = self.bot.send_message(c.message.chat.id, text, reply_markup=skb.CLEAR_STATE_BTN())
        self.set_state(c.message.chat.id, result.id, c.from_user.id, CBT.EDIT_ORDER_CONFIRM_REPLY_TEXT)
        self.bot.answer_callback_query(c.id)

    def edit_order_confirm_reply_text(self, m: Message):
        self.clear_state(m.chat.id, m.from_user.id, True)
        if "OrderConfirm" not in self.cardinal.MAIN_CFG:
            self.cardinal.MAIN_CFG["OrderConfirm"] = {}
        self.cardinal.MAIN_CFG["OrderConfirm"]["replyText"] = m.text
        logger.info(_("log_order_confirm_changed", m.from_user.username, m.from_user.id, m.text))
        self.cardinal.save_config(self.cardinal.MAIN_CFG, "configs/_main.cfg")
        keyboard = K() \
            .row(B(_("gl_back"), callback_data=f"{CBT.CATEGORY}:oc"),
                 B(_("gl_edit"), callback_data=CBT.EDIT_ORDER_CONFIRM_REPLY_TEXT))
        self.bot.reply_to(m, _("order_confirm_changed"), reply_markup=keyboard)

    def open_reply_menu(self, c: CallbackQuery):
        """
        Открывает меню ответа на сообщение (callback используется в кнопках "назад").
        """
        split = c.data.split(":")
        # В PlayerokAPI node_id это UUID (строка), а не int
        node_id = str(split[1])
        again = int(split[2])
        extend = True if len(split) > 3 and int(split[3]) else False
        # Получаем username из чата
        try:
            chat = self.cardinal.account.get_chat(node_id)
            username = chat.users[0].username if chat.users and hasattr(chat.users[0], 'username') else str(chat.users[0].id) if chat.users else ""
        except Exception as e:
            logger.error(f"Ошибка получения чата {node_id}: {e}")
            username = ""
        self.bot.edit_message_reply_markup(c.message.chat.id, c.message.id,
                                           reply_markup=kb.reply(node_id, username, bool(again), extend))

    def extend_new_message_notification(self, c: CallbackQuery):
        """
        "Расширяет" уведомление о новом сообщении.
        """
        chat_id = c.data.split(":")[1]
        try:
            # В PlayerokAPI chat_id это UUID (строка), а не int
            chat = self.cardinal.account.get_chat(str(chat_id))
            # Получаем username из чата
            username = chat.users[0].username if chat.users and hasattr(chat.users[0], 'username') else str(chat.users[0].id) if chat.users else ""
            # Получаем сообщения через API
            messages_list = self.cardinal.account.get_chat_messages(str(chat_id), 10)
            messages = messages_list.messages if messages_list and messages_list.messages else []
        except Exception as e:
            logger.error(f"Ошибка получения чата {chat_id}: {e}")
            self.bot.answer_callback_query(c.id)
            self.bot.send_message(c.message.chat.id, _("get_chat_error"))
            return

        text = f"<b>💬 История сообщений с {username}</b>\n\n"
        
        # В PlayerokAPI Chat не имеет messages напрямую, получаем через API
        if messages:
            for msg in messages[-10:]:
                # Получаем автора сообщения
                if hasattr(msg, 'user') and msg.user:
                    author_username = msg.user.username if hasattr(msg.user, 'username') else str(msg.user.id)
                    author_id = str(msg.user.id)
                else:
                    author_username = "Unknown"
                    author_id = ""
                
                # Определяем, от кого сообщение
                if author_id == str(self.cardinal.account.id):
                    author = f"<i><b>🫵 {_('you')}:</b></i> "
                elif author_username in self.cardinal.blacklist:
                    author = f"<i><b>🚷 {author_username}: </b></i>"
                else:
                    author = f"<i><b>👤 {author_username}: </b></i>"
                
                # Формируем текст сообщения
                msg_text = ""
                if msg.text:
                    msg_text = f"<code>{utils.escape(msg.text)}</code>"
                elif hasattr(msg, 'file') and msg.file:
                    msg_text = f"<a href=\"{msg.file.url if hasattr(msg.file, 'url') else '#'}\">{_('photo')}</a>"
                else:
                    msg_text = "[Медиа]"
                
                text += f"{author}{msg_text}\n\n"
        else:
            text += "<i>Сообщений не найдено</i>"

        # Создаем клавиатуру
        from telebot.types import InlineKeyboardMarkup as K, InlineKeyboardButton as B
        from tg_bot import CBT
        
        keyboard = K()
        keyboard.row(
            B(_("msg_reply"), None, f"{CBT.SEND_FP_MESSAGE}:{chat_id}"),
            B(_("msg_templates"), None, f"{CBT.TMPLT_LIST_ANS_MODE}:0:{chat_id}:0:0")
        )
        keyboard.row(B(f"🌐 {username}", url=f"https://playerok.com/chats/{chat_id}"))
        
        self.bot.edit_message_text(text, c.message.chat.id, c.message.id,
                                   reply_markup=keyboard)
        self.bot.answer_callback_query(c.id)

    # Ордер
    def ask_confirm_refund(self, call: CallbackQuery):
        """
        Просит подтвердить возврат денег.
        """
        split = call.data.split(":")
        order_id, node_id = split[1], str(split[2])  # node_id это UUID (строка)
        # Получаем username из чата
        try:
            chat = self.cardinal.account.get_chat(node_id)
            username = chat.users[0].username if chat.users and hasattr(chat.users[0], 'username') else str(chat.users[0].id) if chat.users else ""
        except Exception as e:
            logger.error(f"Ошибка получения чата {node_id}: {e}")
            username = ""
        keyboard = kb.new_order(order_id, username, node_id, confirmation=True)
        self.bot.edit_message_reply_markup(call.message.chat.id, call.message.id, reply_markup=keyboard)
        self.bot.answer_callback_query(call.id)

    def cancel_refund(self, call: CallbackQuery):
        """
        Отменяет возврат.
        """
        split = call.data.split(":")
        order_id, node_id = split[1], str(split[2])  # node_id это UUID (строка)
        # Получаем username из чата
        try:
            chat = self.cardinal.account.get_chat(node_id)
            username = chat.users[0].username if chat.users and hasattr(chat.users[0], 'username') else str(chat.users[0].id) if chat.users else ""
        except Exception as e:
            logger.error(f"Ошибка получения чата {node_id}: {e}")
            username = ""
        keyboard = kb.new_order(order_id, username, node_id)
        self.bot.edit_message_reply_markup(call.message.chat.id, call.message.id, reply_markup=keyboard)
        self.bot.answer_callback_query(call.id)

    def refund(self, c: CallbackQuery):
        """
        Оформляет возврат за заказ.
        """
        split = c.data.split(":")
        order_id, node_id = split[1], str(split[2])  # node_id это UUID (строка)
        # Получаем username из чата
        try:
            chat = self.cardinal.account.get_chat(node_id)
            username = chat.users[0].username if chat.users and hasattr(chat.users[0], 'username') else str(chat.users[0].id) if chat.users else ""
        except Exception as e:
            logger.error(f"Ошибка получения чата {node_id}: {e}")
            username = ""
        new_msg = None
        attempts = 3
        while attempts:
            try:
                # В PlayerokAPI используется update_deal вместо refund
                from PlayerokAPI import enums
                self.cardinal.account.update_deal(order_id, enums.ItemDealStatuses.ROLLED_BACK)
                break
            except:
                if not new_msg:
                    new_msg = self.bot.send_message(c.message.chat.id, _("refund_attempt", order_id, attempts))
                else:
                    self.bot.edit_message_text(_("refund_attempt", order_id, attempts), new_msg.chat.id, new_msg.id)
                attempts -= 1
                time.sleep(1)

        else:
            self.bot.edit_message_text(_("refund_error", order_id), new_msg.chat.id, new_msg.id)

            keyboard = kb.new_order(order_id, username, node_id)
            self.bot.edit_message_reply_markup(c.message.chat.id, c.message.id, reply_markup=keyboard)
            self.bot.answer_callback_query(c.id)
            return

        if not new_msg:
            self.bot.send_message(c.message.chat.id, _("refund_complete", order_id))
        else:
            self.bot.edit_message_text(_("refund_complete", order_id), new_msg.chat.id, new_msg.id)

        keyboard = kb.new_order(order_id, username, node_id, no_refund=True)
        self.bot.edit_message_reply_markup(c.message.chat.id, c.message.id, reply_markup=keyboard)
        self.bot.answer_callback_query(c.id)

    def open_order_menu(self, c: CallbackQuery):
        split = c.data.split(":")
        node_id = str(split[1])  # UUID (строка)
        order_id = split[2] if len(split) > 2 else ""
        no_refund = bool(int(split[3])) if len(split) > 3 else False
        # Получаем username из чата
        try:
            chat = self.cardinal.account.get_chat(node_id)
            username = chat.users[0].username if chat.users and hasattr(chat.users[0], 'username') else str(chat.users[0].id) if chat.users else ""
        except Exception as e:
            logger.error(f"Ошибка получения чата {node_id}: {e}")
            username = ""
        self.bot.edit_message_reply_markup(c.message.chat.id, c.message.id,
                                           reply_markup=kb.new_order(order_id, username, node_id, no_refund=no_refund))

    # Панель управления
    def open_cp(self, c: CallbackQuery):
        """
        Открывает основное меню настроек (редактирует сообщение).
        """
        try:
            self.bot.edit_message_text(_("desc_main"), c.message.chat.id, c.message.id,
                                       reply_markup=skb.SETTINGS_SECTIONS())
        except Exception as e:
            if "message is not modified" not in str(e):
                raise
        self.bot.answer_callback_query(c.id)

    def open_cp2(self, c: CallbackQuery):
        """
        Открывает 2 страницу основного меню настроек (редактирует сообщение).
        """
        try:
            self.bot.edit_message_text(_("desc_main"), c.message.chat.id, c.message.id,
                                       reply_markup=skb.SETTINGS_SECTIONS_2())
        except Exception as e:
            if "message is not modified" not in str(e):
                raise
        self.bot.answer_callback_query(c.id)

    def switch_param(self, c: CallbackQuery):
        """
        Переключает переключаемые настройки POC.
        """
        split = c.data.split(":")
        section, option = split[1], split[2]
        if (section == "FunPay" or section == "Playerok") and option == "oldMsgGetMode":
            self.cardinal.switch_msg_get_mode()
        else:
            if section not in self.cardinal.MAIN_CFG:
                self.cardinal.MAIN_CFG[section] = {}
            if option not in self.cardinal.MAIN_CFG[section]:
                self.cardinal.MAIN_CFG[section][option] = "0"
            self.cardinal.MAIN_CFG[section][option] = str(int(not int(self.cardinal.MAIN_CFG[section][option])))
            self.cardinal.save_config(self.cardinal.MAIN_CFG, "configs/_main.cfg")

        sections = {
            "FunPay": kb.main_settings,
            "Playerok": kb.main_settings,  # Playerok использует те же настройки что и FunPay
            "BlockList": kb.blacklist_settings,
            "NewMessageView": kb.new_message_view_settings,
            "Greetings": kb.greeting_settings,
            "OrderConfirm": kb.order_confirm_reply_settings,
        }
        if section == "Telegram":
            self.bot.edit_message_reply_markup(c.message.chat.id, c.message.id,
                                               reply_markup=kb.authorized_users(self.cardinal, offset=int(split[3])))
        elif section in sections:
            self.bot.edit_message_reply_markup(c.message.chat.id, c.message.id,
                                               reply_markup=sections[section](self.cardinal))
        else:
            logger.warning(f"Неизвестная секция настроек: {section}")
            self.bot.answer_callback_query(c.id, text="Неизвестная секция настроек", show_alert=True)
        logger.info(_("log_param_changed", c.from_user.username, c.from_user.id, option, section,
                      self.cardinal.MAIN_CFG[section][option]))
        self.bot.answer_callback_query(c.id)

    def switch_chat_notification(self, c: CallbackQuery):
        split = c.data.split(":")
        chat_id, notification_type = int(split[1]), split[2]

        result = self.toggle_notification(chat_id, notification_type)
        logger.info(_("log_notification_switched", c.from_user.username, c.from_user.id,
                      notification_type, c.message.chat.id, result))
        keyboard = kb.announcements_settings if notification_type in [utils.NotificationTypes.announcement,
                                                                      utils.NotificationTypes.ad] \
            else kb.notifications_settings
        self.bot.edit_message_reply_markup(c.message.chat.id, c.message.id,
                                           reply_markup=keyboard(self.cardinal, c.message.chat.id))
        self.bot.answer_callback_query(c.id)

    def switch_restore_priority(self, c: CallbackQuery):
        """
        Переключает режим авто-восстановления (free <-> premium).
        """
        current_mode = self.cardinal.MAIN_CFG.get("Playerok", {}).get("restorePriorityMode", "premium")
        
        if current_mode == "free":
            new_mode = "premium"
        else:
            new_mode = "free"
        
        if "Playerok" not in self.cardinal.MAIN_CFG:
            self.cardinal.MAIN_CFG["Playerok"] = {}
        self.cardinal.MAIN_CFG["Playerok"]["restorePriorityMode"] = new_mode
        self.cardinal.save_config(self.cardinal.MAIN_CFG, "configs/_main.cfg")
        
        mode_text = {"free": "Бесплатно", "premium": "Премиум"}[new_mode]
        logger.info(f"Режим авто-восстановления изменен на {new_mode} пользователем {c.from_user.username} (id: {c.from_user.id})")
        
        self.bot.edit_message_reply_markup(c.message.chat.id, c.message.id,
                                           reply_markup=kb.main_settings(self.cardinal))
        self.bot.answer_callback_query(c.id, text=f"Режим восстановления: {mode_text}", show_alert=False)

    def open_settings_section(self, c: CallbackQuery):
        """
        Открывает выбранную категорию настроек.
        """
        if c.from_user.id not in self.authorized_users:
            self.ignore_unauthorized_users(c)
            return
        section = c.data.split(":")[1]
        sections = {
            "lang": (_("desc_lang"), kb.language_settings, [self.cardinal]),
            "main": (_("desc_gs"), kb.main_settings, [self.cardinal]),
            "tg": (_("desc_ns", c.message.chat.id), kb.notifications_settings, [self.cardinal, c.message.chat.id]),
            "bl": (_("desc_bl"), kb.blacklist_settings, [self.cardinal]),
            "ar": (_("desc_ar"), skb.AR_SETTINGS, []),
            "ad": (_("desc_ad"), skb.AD_SETTINGS, []),
            "mv": (_("desc_mv"), kb.new_message_view_settings, [self.cardinal]),
            "gr": (_("desc_gr", utils.escape(self.cardinal.MAIN_CFG.get('Greetings', {}).get('greetingsText', ''))),
                   kb.greeting_settings, [self.cardinal]),
            "oc": (_("desc_oc", utils.escape(self.cardinal.MAIN_CFG.get('OrderConfirm', {}).get('replyText', ''))),
                   kb.order_confirm_reply_settings, [self.cardinal])
        }

        curr = sections[section]
        try:
            self.bot.edit_message_text(curr[0], c.message.chat.id, c.message.id, reply_markup=curr[1](*curr[2]))
        except Exception as e:
            if "message is not modified" not in str(e):
                raise
        self.bot.answer_callback_query(c.id)

    # Прочее
    def cancel_action(self, call: CallbackQuery):
        """
        Обнуляет состояние пользователя по кнопке "Отмена" (CBT.CLEAR_STATE).
        """
        result = self.clear_state(call.message.chat.id, call.from_user.id, True)
        if result is None:
            self.bot.answer_callback_query(call.id)

    def param_disabled(self, c: CallbackQuery):
        """
        Отправляет сообщение о том, что параметр отключен в глобальных переключателях.
        """
        self.bot.answer_callback_query(c.id, _("param_disabled"), show_alert=True)

    def send_announcements_kb(self, m: Message):
        """
        Отправляет сообщение с клавиатурой управления уведомлениями о новых объявлениях.
        """
        if m.from_user.id not in self.authorized_users:
            self.reg_admin(m)
            return
        self.bot.send_message(m.chat.id, _("desc_an"), reply_markup=kb.announcements_settings(self.cardinal, m.chat.id))

    def send_old_mode_help_text(self, c: CallbackQuery):
        self.bot.answer_callback_query(c.id)
        self.bot.send_message(c.message.chat.id, _("old_mode_help"))

    def empty_callback(self, c: CallbackQuery):
        self.bot.answer_callback_query(c.id, "👨‍💻 @KaDerix 👨‍💻")

    def switch_lang(self, c: CallbackQuery):
        lang = c.data.split(":")[1]
        Localizer(lang)
        if "Other" not in self.cardinal.MAIN_CFG:
            self.cardinal.MAIN_CFG["Other"] = {}
        self.cardinal.MAIN_CFG["Other"]["language"] = lang
        self.cardinal.save_config(self.cardinal.MAIN_CFG, "configs/_main.cfg")
        if localizer.current_language == "en":
            self.bot.answer_callback_query(c.id, "The translation may be incomplete and contain errors.\n\n"
                                                 "If you find errors in the translation, let @KaDerix know.\n\n"
                                                 "Thank you :)", show_alert=True)
        elif localizer.current_language == "uk":
            self.bot.answer_callback_query(c.id, "Переклад складено за допомогою ChatGPT.\n"
                                                 "Повідомте @KaDerix, якщо знайдете помилки.", show_alert=True)
        elif localizer.current_language == "ru":
            self.bot.answer_callback_query(c.id, '«А я сейчас вам покажу, откуда на Беларусь готовилось нападение»',
                                           show_alert=True)
        c.data = f"{CBT.CATEGORY}:lang"
        self.open_settings_section(c)

    def __register_handlers(self):
        """
        Регистрирует хэндлеры всех команд.
        """
        self.mdw_handler(self.setup_chat_notifications, update_types=['message'])
        self.msg_handler(self.reg_admin, func=lambda msg: msg.from_user.id not in self.authorized_users,
                         content_types=['text', 'document', 'photo', 'sticker'])
        self.cbq_handler(self.ignore_unauthorized_users, lambda c: c.from_user.id not in self.authorized_users)
        self.cbq_handler(self.param_disabled, lambda c: c.data.startswith(CBT.PARAM_DISABLED))
        self.msg_handler(self.run_file_handlers, content_types=["photo", "document"],
                         func=lambda m: self.is_file_handler(m))

        self.msg_handler(self.send_settings_menu, commands=["menu", "start"])
        self.msg_handler(self.send_profile, commands=["profile"])
        self.msg_handler(self.act_change_cookie, commands=["change_cookie", "token"])
        self.msg_handler(self.change_cookie, func=lambda m: self.check_state(m.chat.id, m.from_user.id,
                                                                             CBT.CHANGE_GOLDEN_KEY))
        self.cbq_handler(self.update_profile, lambda c: c.data == CBT.UPDATE_PROFILE)
        self.msg_handler(self.act_manual_delivery_test, commands=["test_lot"])
        self.msg_handler(self.act_upload_image, commands=["upload_chat_img", "upload_offer_img"])
        self.msg_handler(self.act_upload_backup, commands=["upload_backup"])
        self.cbq_handler(self.act_edit_greetings_text, lambda c: c.data == CBT.EDIT_GREETINGS_TEXT)
        self.msg_handler(self.edit_greetings_text,
                         func=lambda m: self.check_state(m.chat.id, m.from_user.id, CBT.EDIT_GREETINGS_TEXT))
        self.cbq_handler(self.act_edit_greetings_cooldown, lambda c: c.data == CBT.EDIT_GREETINGS_COOLDOWN)
        self.msg_handler(self.edit_greetings_cooldown,
                         func=lambda m: self.check_state(m.chat.id, m.from_user.id, CBT.EDIT_GREETINGS_COOLDOWN))
        self.cbq_handler(self.act_edit_order_confirm_reply_text, lambda c: c.data == CBT.EDIT_ORDER_CONFIRM_REPLY_TEXT)
        self.msg_handler(self.edit_order_confirm_reply_text,
                         func=lambda m: self.check_state(m.chat.id, m.from_user.id, CBT.EDIT_ORDER_CONFIRM_REPLY_TEXT))
        self.msg_handler(self.manual_delivery_text,
                         func=lambda m: self.check_state(m.chat.id, m.from_user.id, CBT.MANUAL_AD_TEST))
        self.msg_handler(self.act_ban, commands=["ban"])
        self.msg_handler(self.ban, func=lambda m: self.check_state(m.chat.id, m.from_user.id, CBT.BAN))
        self.msg_handler(self.act_unban, commands=["unban"])
        self.msg_handler(self.unban, func=lambda m: self.check_state(m.chat.id, m.from_user.id, CBT.UNBAN))
        self.msg_handler(self.send_ban_list, commands=["black_list"])
        self.msg_handler(self.act_edit_watermark, commands=["watermark"])
        self.msg_handler(self.edit_watermark,
                         func=lambda m: self.check_state(m.chat.id, m.from_user.id, CBT.EDIT_WATERMARK))
        self.msg_handler(self.send_logs, commands=["logs"])
        self.msg_handler(self.del_logs, commands=["del_logs"])
        self.msg_handler(self.about, commands=["about"])
        self.msg_handler(self.check_updates, commands=["check_updates"])
        self.msg_handler(self.update, commands=["update"])
        self.msg_handler(self.get_backup, commands=["get_backup"])
        self.msg_handler(self.create_backup, commands=["create_backup"])
        self.msg_handler(self.send_system_info, commands=["sys"])
        self.msg_handler(self.restart_cardinal, commands=["restart"])
        self.msg_handler(self.ask_power_off, commands=["power_off"])
        self.msg_handler(self.send_announcements_kb, commands=["announcements"])
        self.cbq_handler(self.act_send_funpay_message, lambda c: c.data.startswith(f"{CBT.SEND_FP_MESSAGE}:"))
        self.cbq_handler(self.open_reply_menu, lambda c: c.data.startswith(f"{CBT.BACK_TO_REPLY_KB}:"))
        self.cbq_handler(self.extend_new_message_notification, lambda c: c.data.startswith(f"{CBT.EXTEND_CHAT}:"))
        self.msg_handler(self.send_funpay_message,
                         func=lambda m: self.check_state(m.chat.id, m.from_user.id, CBT.SEND_FP_MESSAGE))
        self.cbq_handler(self.ask_confirm_refund, lambda c: c.data.startswith(f"{CBT.REQUEST_REFUND}:"))
        self.cbq_handler(self.cancel_refund, lambda c: c.data.startswith(f"{CBT.REFUND_CANCELLED}:"))
        self.cbq_handler(self.refund, lambda c: c.data.startswith(f"{CBT.REFUND_CONFIRMED}:"))
        self.cbq_handler(self.open_order_menu, lambda c: c.data.startswith(f"{CBT.BACK_TO_ORDER_KB}:"))
        self.cbq_handler(self.open_cp, lambda c: c.data == CBT.MAIN)
        self.cbq_handler(self.open_cp2, lambda c: c.data == CBT.MAIN2)
        self.cbq_handler(self.open_settings_section, lambda c: c.data.startswith(f"{CBT.CATEGORY}:"))
        self.cbq_handler(self.switch_param, lambda c: c.data.startswith(f"{CBT.SWITCH}:"))
        self.cbq_handler(self.switch_chat_notification, lambda c: c.data.startswith(f"{CBT.SWITCH_TG_NOTIFICATIONS}:"))
        self.cbq_handler(self.switch_restore_priority, lambda c: c.data == CBT.SWITCH_RESTORE_PRIORITY)
        self.cbq_handler(self.power_off, lambda c: c.data.startswith(f"{CBT.SHUT_DOWN}:"))
        self.cbq_handler(self.cancel_power_off, lambda c: c.data == CBT.CANCEL_SHUTTING_DOWN)
        self.cbq_handler(self.cancel_action, lambda c: c.data == CBT.CLEAR_STATE)
        self.cbq_handler(self.send_old_mode_help_text, lambda c: c.data == CBT.OLD_MOD_HELP)
        self.cbq_handler(self.empty_callback, lambda c: c.data == CBT.EMPTY)
        self.cbq_handler(self.switch_lang, lambda c: c.data.startswith(f"{CBT.LANG}:"))

    def send_notification(self, text: str | None, keyboard: K | None = None,
                          notification_type: str = utils.NotificationTypes.other, photo: bytes | None = None,
                          pin: bool = False):
        """
        Отправляет сообщение во все чаты для уведомлений из self.notification_settings.

        :param text: текст уведомления.
        :param keyboard: экземпляр клавиатуры.
        :param notification_type: тип уведомления.
        :param photo: фотография (если нужна).
        :param pin: закреплять ли сообщение.
        """
        kwargs = {}
        if keyboard is not None:
            kwargs["reply_markup"] = keyboard
        to_delete = []
        for chat_id in self.notification_settings:
            if notification_type != utils.NotificationTypes.important_announcement and \
                    not self.is_notification_enabled(chat_id, notification_type):
                continue

            try:
                if photo:
                    msg = self.bot.send_photo(chat_id, photo, text, **kwargs)
                else:
                    msg = self.bot.send_message(chat_id, text, **kwargs)

                if notification_type == utils.NotificationTypes.bot_start:
                    self.init_messages.append((msg.chat.id, msg.id))

                if pin:
                    self.bot.pin_chat_message(msg.chat.id, msg.id)
            except Exception as e:
                logger.error(_("log_tg_notification_error", chat_id))
                logger.debug("TRACEBACK", exc_info=True)
                if isinstance(e, ApiTelegramException) and (
                        e.result.status_code == 403 or e.result.status_code == 400 and
                        (e.result_json.get('description') in \
                         ("Bad Request: group chat was upgraded to a supergroup chat", "Bad Request: chat not found"))):
                    to_delete.append(chat_id)
                continue
        for chat_id in to_delete:
            if chat_id in self.notification_settings:
                del self.notification_settings[chat_id]
                utils.save_notification_settings(self.notification_settings)

    def add_command_to_menu(self, command: str, help_text: str) -> None:
        """
        Добавляет команду в список команд (в кнопке menu).

        :param command: текст команды.

        :param help_text: текст справки.
        """
        self.commands[command] = help_text
    
    def update_commands_menu(self):
        """
        Обновляет меню команд бота (вызывается после загрузки плагинов).
        """
        self.setup_commands()

    def setup_commands(self):
        """
        Устанавливает меню команд.
        """
        for lang in (None, *localizer.languages.keys()):
            commands = []
            for cmd in self.commands:
                # Если значение - это ключ локализации (начинается с "cmd_"), переводим его
                # Если значение - это уже текст (от плагина), используем как есть
                help_text = self.commands[cmd]
                if help_text.startswith("cmd_") and hasattr(localizer, 'translate'):
                    # Это ключ локализации, переводим
                    translated = _(help_text, language=lang)
                else:
                    # Это уже текст от плагина, используем как есть
                    translated = help_text
                commands.append(BotCommand(f"/{cmd}", translated))
            self.bot.set_my_commands(commands, language_code=lang)

    def edit_bot(self):
        """
        Изменяет описания и название бота.
        """

        name = self.bot.get_me().full_name
        limit = 64
        add_to_name = ["Playerok Bot | Бот Плейерок", "Playerok Bot", "PlayerokBot", "Playerok"]
        new_name = name
        if "vertex" in new_name.lower():
            new_name = ""
        new_name = new_name.split("ㅤ")[0].strip()
        if "playerok" not in new_name.lower():
            for m_name in add_to_name:
                if len(new_name) + 2 + len(m_name) <= limit:
                    new_name = f"{(new_name + ' ').ljust(limit - len(m_name) - 1, 'ㅤ')} {m_name}"
                    break
            if new_name != name:
                self.bot.set_my_name(new_name)
        sh_text = "🛠️ Playerok Cardinal - Бот для автоматизации работы с Playerok"
        res = self.bot.get_my_short_description().short_description
        if res != sh_text:
            self.bot.set_my_short_description(sh_text)
        for i in [None, *localizer.languages.keys()]:
            res = self.bot.get_my_description(i).description
            text = _("adv_description", self.cardinal.VERSION, language=i)
            if res != text:
                self.bot.set_my_description(text, language_code=i)

    def init(self):
        self.__register_handlers()
        self.setup_commands()
        self.edit_bot()
        logger.info(_("log_tg_initialized"))

    def run(self):
        """
        Запускает поллинг.
        """
        self.send_notification(_("bot_started"), notification_type=utils.NotificationTypes.bot_start)
        k_err = 0
        while True:
            try:
                logger.info(_("log_tg_started", self.bot.user.username))
                self.bot.infinity_polling(logger_level=logging.DEBUG)
            except:
                k_err += 1
                logger.error(_("log_tg_update_error", k_err))
                logger.debug("TRACEBACK", exc_info=True)
                time.sleep(10)

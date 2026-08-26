"""
В данном модуле описаны функции для ПУ настроек прокси.
Модуль реализован в виде плагина.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING
from tg_bot import utils, static_keyboards as skb, keyboards as kb, CBT
import telebot.apihelper
from Utils.cardinal_tools import validate_proxy, cache_proxy_dict, check_proxy
from telebot.types import InlineKeyboardMarkup as K, InlineKeyboardButton as B

if TYPE_CHECKING:
    from cardinal import Cardinal
from tg_bot import keyboards as kb, CBT
from telebot.types import CallbackQuery, Message
import logging
from threading import Thread
from locales.localizer import Localizer

logger = logging.getLogger("TGBot")
localizer = Localizer()
_ = localizer.translate


def init_proxy_cp(crd: Cardinal, *args):
    tg = crd.telegram
    bot = tg.bot
    pr_dict = {}

    def check_one_proxy(proxy: str):
        try:
            d = {
                "http": f"http://{proxy}",
                "https": f"http://{proxy}"
            }
            pr_dict[proxy] = check_proxy(d)
        except Exception as e:
            # Не логируем ошибки проверки прокси, чтобы не спамить логи
            # Только в режиме отладки
            logger.debug(f"Ошибка проверки прокси {proxy}: {e}")
            pr_dict[proxy] = False

    def check_proxies():
        proxy_section = crd.MAIN_CFG.get("Proxy", {})
        if isinstance(proxy_section, dict):
            enable = proxy_section.get("enable", "0") == "1"
            check = proxy_section.get("check", "0") == "1"
        else:
            enable = proxy_section.getboolean("enable")
            check = proxy_section.getboolean("check")
        
        if enable and check:
            # Ждем 10 секунд перед первой проверкой, чтобы избежать конфликта с проверкой при инициализации
            time.sleep(10)
            while True:
                for proxy in crd.proxy_dict.values():
                    try:
                        # Пропускаем проверку если прокси уже используется в account
                        if hasattr(crd, 'account') and crd.account and hasattr(crd.account, 'proxy'):
                            current_proxy = crd.account.proxy
                            if current_proxy:
                                # Если это текущий прокси, пропускаем проверку (он уже проверен при инициализации)
                                proxy_dict = {
                                    "http": f"http://{proxy}",
                                    "https": f"http://{proxy}"
                                }
                                if current_proxy == proxy_dict or (isinstance(current_proxy, str) and proxy in current_proxy):
                                    continue
                        check_one_proxy(proxy)
                    except Exception as e:
                        # Не логируем ошибки проверки прокси в фоне, чтобы не спамить логи
                        logger.debug(f"Ошибка проверки прокси {proxy}: {e}")
                        pass
                time.sleep(3600)

    Thread(target=check_proxies, daemon=True).start()

    def open_proxy_list(c: CallbackQuery):
        """
        Открывает список прокси.
        """
        offset = int(c.data.split(":")[1])
        
        proxy_section = crd.MAIN_CFG.get("Proxy", {})
        if isinstance(proxy_section, dict):
            enable = "вкл." if proxy_section.get("enable", "0") == "1" else "выкл."
            check = "вкл." if proxy_section.get("check", "0") == "1" else "выкл."
        else:
            enable = "вкл." if proxy_section.getboolean("enable") else "выкл."
            check = "вкл." if proxy_section.getboolean("check") else "выкл."
        
        text = f'\n\nПрокси: {enable}\n' \
               f'Проверка прокси: {check}'
        bot.edit_message_text(f'{_("desc_proxy")}{text}', c.message.chat.id, c.message.id,
                              reply_markup=kb.proxy(crd, offset, pr_dict))

    def act_add_proxy(c: CallbackQuery):
        """
        Активирует режим ввода прокси для добавления.
        """
        offset = int(c.data.split(":")[-1])
        result = bot.send_message(c.message.chat.id, _("act_proxy"), reply_markup=skb.CLEAR_STATE_BTN())
        crd.telegram.set_state(result.chat.id, result.id, c.from_user.id, CBT.ADD_PROXY, {"offset": offset})
        bot.answer_callback_query(c.id)

    def add_proxy(m: Message):
        """
        Добавляет прокси.
        """
        offset = tg.get_state(m.chat.id, m.from_user.id)["data"]["offset"]
        kb = K().add(B(_("gl_back"), callback_data=f"{CBT.PROXY}:{offset}"))
        tg.clear_state(m.chat.id, m.from_user.id, True)
        proxy = m.text
        try:
            login, password, ip, port = validate_proxy(proxy)
            proxy_str = f"{f'{login}:{password}@' if login and password else ''}{ip}:{port}"
            if proxy_str in crd.proxy_dict.values():
                bot.send_message(m.chat.id, _("proxy_already_exists").format(utils.escape(proxy_str)), reply_markup=kb)
                return
            # Получаем максимальный числовой ключ, фильтруя нечисловые
            numeric_keys = [k for k in crd.proxy_dict.keys() if isinstance(k, int)]
            max_id = max(numeric_keys, default=-1) if numeric_keys else -1
            crd.proxy_dict[max_id + 1] = proxy_str
            cache_proxy_dict(crd.proxy_dict)
            bot.send_message(m.chat.id, _("proxy_added").format(utils.escape(proxy_str)), reply_markup=kb)
            Thread(target=check_one_proxy, args=(proxy_str,), daemon=True).start()
        except ValueError:
            bot.send_message(m.chat.id, _("proxy_format"), reply_markup=kb)
        except:
            bot.send_message(m.chat.id, _("proxy_adding_error"), reply_markup=kb)
            logger.debug("TRACEBACK", exc_info=True)

    def choose_proxy(c: CallbackQuery):
        """
        Выбор прокси из списка.
        """
        try:
            q, offset, proxy_id = c.data.split(":")
            offset = int(offset)
            # Пытаемся преобразовать proxy_id в int
            try:
                proxy_id = int(proxy_id)
            except ValueError:
                # Если proxy_id не число, значит это старый формат или ошибка
                logger.error(f"Некорректный proxy_id в callback_data: {proxy_id}")
                bot.answer_callback_query(c.id, text="Ошибка: некорректный формат прокси", show_alert=True)
                open_proxy_list(c)
                return
            proxy = crd.proxy_dict.get(proxy_id)
            c.data = f"{CBT.PROXY}:{offset}"
            if not proxy:
                open_proxy_list(c)
                return
        except (ValueError, IndexError) as e:
            logger.error(f"Ошибка парсинга callback_data для choose_proxy: {c.data}, ошибка: {e}")
            bot.answer_callback_query(c.id, text="Ошибка: некорректный формат данных", show_alert=True)
            return

        login, password, ip, port = validate_proxy(proxy)
        proxy = f"{f'{login}:{password}@' if login and password else ''}{ip}:{port}"
        proxy = {
            "http": f"http://{proxy}",
            "https": f"http://{proxy}"
        }
        crd.MAIN_CFG["Proxy"].update({
            "ip": ip,
            "port": port,
            "login": login,
            "password": password
        })
        crd.save_config(crd.MAIN_CFG, "configs/_main.cfg")
        proxy_section = crd.MAIN_CFG.get("Proxy", {})
        if isinstance(proxy_section, dict):
            enable = proxy_section.get("enable", "0") == "1"
        else:
            enable = proxy_section.getboolean("enable")
        if enable:
            crd.account.proxy = proxy
        open_proxy_list(c)

    def delete_proxy(c: CallbackQuery):
        """
        Удаление прокси.
        """
        q, offset, proxy_id = c.data.split(":")
        offset = int(offset)
        proxy_id = int(proxy_id)
        c.data = f"{CBT.PROXY}:{offset}"
        if proxy_id in crd.proxy_dict.keys():
            proxy = crd.proxy_dict[proxy_id]
            login, password, ip, port = validate_proxy(proxy)
            now_proxy = crd.account.proxy
            if not now_proxy or now_proxy.get("http").replace("http://", "", 1) != proxy:
                del crd.proxy_dict[proxy_id]
                cache_proxy_dict(crd.proxy_dict)
                if proxy in pr_dict:
                    del pr_dict[proxy]
                logger.info(f"Прокси {proxy} удалены.")
                if str(crd.MAIN_CFG["Proxy"]["ip"]) == str(ip) and str(crd.MAIN_CFG["Proxy"]["login"]) == str(login) \
                        and str(crd.MAIN_CFG["Proxy"]["port"]) == str(port) \
                        and str(crd.MAIN_CFG["Proxy"]["password"]) == str(password):
                    for i in ("password", "port", "login", "ip"):
                        crd.MAIN_CFG["Proxy"][i] = ""
                    crd.save_config(crd.MAIN_CFG, "configs/_main.cfg")
            else:
                bot.answer_callback_query(c.id, _("proxy_undeletable"), show_alert=True)
                return

        open_proxy_list(c)

    tg.cbq_handler(open_proxy_list, lambda c: c.data.startswith(f"{CBT.PROXY}:"))
    tg.cbq_handler(act_add_proxy, lambda c: c.data.startswith(f"{CBT.ADD_PROXY}:"))
    tg.cbq_handler(choose_proxy, lambda c: c.data.startswith(f"{CBT.CHOOSE_PROXY}:"))
    tg.cbq_handler(delete_proxy, lambda c: c.data.startswith(f"{CBT.DELETE_PROXY}:"))
    tg.msg_handler(add_proxy, func=lambda m: crd.telegram.check_state(m.chat.id, m.from_user.id, CBT.ADD_PROXY))


BIND_TO_PRE_INIT = [init_proxy_cp]

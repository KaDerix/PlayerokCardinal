"""
В данном модуле описаны функции для ПУ настроек прокси.
Модуль реализован в виде плагина.
"""

from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from cardinal import Cardinal
from telebot.types import CallbackQuery, Message
import logging

from locales.localizer import Localizer

logger = logging.getLogger("TGBot")
localizer = Localizer()
_ = localizer.translate


def init_default_cp(crd: Cardinal, *args):
    tg = crd.telegram
    bot = tg.bot

    def default_callback_answer(c: CallbackQuery):
        """
        Отвечает на колбеки, которые не поймал ни один хендлер.
        ВАЖНО: Этот обработчик отключен, так как он мешает работе плагинов.
        Плагины должны регистрировать свои обработчики с правильными фильтрами.
        """
        logger.debug(f"default_callback_answer получил callback: {c.data} (не должен вызываться)")
        # Не обрабатываем callback'и, которые должны обрабатываться плагинами
        # Просто отвечаем на callback_query, чтобы убрать индикатор загрузки
        try:
            bot.answer_callback_query(c.id)
        except:
            pass

    # ОТКЛЮЧЕНО: Этот обработчик мешает работе плагинов, так как перехватывает все callback'и
    # Плагины должны регистрировать свои обработчики с правильными фильтрами
    # tg.cbq_handler(default_callback_answer, lambda c: True)


BIND_TO_PRE_INIT = [init_default_cp]

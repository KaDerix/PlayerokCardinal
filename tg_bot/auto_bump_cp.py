"""TG-панель настроек авто-поднятия."""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from cardinal import Cardinal

from tg_bot import CBT, keyboards as kb
from tg_bot.static_keyboards import CLEAR_STATE_BTN
from telebot.types import CallbackQuery, Message
from Utils import cardinal_tools as ct
import logging

logger = logging.getLogger("TGBot")


def init_auto_bump_cp(crd: Cardinal, *args):
    tg = crd.telegram
    bot = tg.bot

    def act_edit_interval(c: CallbackQuery):
        result = bot.send_message(c.message.chat.id, "Введите интервал в секундах (мин. 300):",
                                  reply_markup=CLEAR_STATE_BTN())
        tg.set_state(c.message.chat.id, result.id, c.from_user.id, CBT.EDIT_AUTO_BUMP_INTERVAL)
        bot.answer_callback_query(c.id)

    def edit_interval(m: Message):
        tg.clear_state(m.chat.id, m.from_user.id, True)
        try:
            interval = int(m.text.strip())
            if interval < 300:
                raise ValueError
        except ValueError:
            bot.reply_to(m, "❌ Укажите целое число не меньше 300.")
            return
        crd.auto_bump_cfg["interval"] = interval
        ct.save_json_config("configs/auto_bump.json", crd.auto_bump_cfg)
        bot.reply_to(m, f"✅ Интервал: {interval} сек.", reply_markup=kb.auto_bump_settings(crd))

    tg.cbq_handler(act_edit_interval, lambda c: c.data == CBT.EDIT_AUTO_BUMP_INTERVAL)
    tg.msg_handler(edit_interval,
                   func=lambda m: tg.check_state(m.chat.id, m.from_user.id, CBT.EDIT_AUTO_BUMP_INTERVAL))


BIND_TO_PRE_INIT = [init_auto_bump_cp]

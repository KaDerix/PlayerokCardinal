"""
ПУ исключений авто-восстановления (лоты / категории).
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from cardinal import Cardinal

from telebot.types import InlineKeyboardMarkup as K, InlineKeyboardButton as B, Message, CallbackQuery
from tg_bot.static_keyboards import CLEAR_STATE_BTN
from tg_bot import CBT, utils
from Utils import auto_restore_exclusions as excl
from locales.localizer import Localizer
import logging

logger = logging.getLogger("TGBot")
localizer = Localizer()
_ = localizer.translate

PAGE_SIZE = 8


def _lots_kb(offset: int = 0) -> K:
    data = excl.load_exclusions()
    lots = data["lots"]
    kb = K()
    page = lots[offset: offset + PAGE_SIZE]
    for item_id in page:
        short = item_id if len(item_id) <= 20 else f"{item_id[:8]}…{item_id[-6:]}"
        kb.add(B(f"❌ {short}", None, f"{CBT.AR_EXCL_DEL_LOT}:{item_id}:{offset}"))
    nav = []
    if offset > 0:
        nav.append(B("⬅️", None, f"{CBT.AR_EXCL_LOTS}:{max(0, offset - PAGE_SIZE)}"))
    if offset + PAGE_SIZE < len(lots):
        nav.append(B("➡️", None, f"{CBT.AR_EXCL_LOTS}:{offset + PAGE_SIZE}"))
    if nav:
        kb.row(*nav)
    kb.add(B(_("ar_excl_add_lot"), None, CBT.AR_EXCL_ADD_LOT))
    kb.add(B(_("ar_excl_pick_lot"), None, f"{CBT.AR_EXCL_PICK_LOT}:0"))
    kb.add(B(_("gl_back"), None, CBT.AR_EXCL))
    return kb


def _cats_kb(offset: int = 0) -> K:
    data = excl.load_exclusions()
    cats = data["categories"]
    kb = K()
    page = cats[offset: offset + PAGE_SIZE]
    for i, cat in enumerate(page):
        real_i = offset + i
        label = cat if len(cat) <= 40 else cat[:37] + "…"
        kb.add(B(f"❌ {label}", None, f"{CBT.AR_EXCL_DEL_CAT}:{real_i}:{offset}"))
    nav = []
    if offset > 0:
        nav.append(B("⬅️", None, f"{CBT.AR_EXCL_CATS}:{max(0, offset - PAGE_SIZE)}"))
    if offset + PAGE_SIZE < len(cats):
        nav.append(B("➡️", None, f"{CBT.AR_EXCL_CATS}:{offset + PAGE_SIZE}"))
    if nav:
        kb.row(*nav)
    kb.add(B(_("ar_excl_add_cat"), None, CBT.AR_EXCL_ADD_CAT))
    kb.add(B(_("ar_excl_add_stars"), None, CBT.AR_EXCL_ADD_STARS))
    kb.add(B(_("gl_back"), None, CBT.AR_EXCL))
    return kb


def _main_kb() -> K:
    data = excl.load_exclusions()
    return K() \
        .add(B(_("ar_excl_lots", len(data["lots"])), None, f"{CBT.AR_EXCL_LOTS}:0")) \
        .add(B(_("ar_excl_cats", len(data["categories"])), None, f"{CBT.AR_EXCL_CATS}:0")) \
        .add(B(_("gl_back"), None, f"{CBT.CATEGORY}:main"))


def _pick_lots_kb(cardinal: Cardinal, offset: int = 0) -> K:
    kb = K()
    all_lots = cardinal.tg_profile.get_common_lots() if getattr(cardinal, "tg_profile", None) else []
    page = all_lots[offset: offset + PAGE_SIZE]
    excluded = set(excl.load_exclusions()["lots"])
    for i, lot in enumerate(page):
        idx = offset + i
        title = (lot.title or lot.description or str(lot.id))[:40]
        mark = "✅ " if str(lot.id) in excluded else ""
        kb.add(B(f"{mark}{title}", None, f"{CBT.AR_EXCL_TOGGLE_LOT}:{idx}:{offset}"))
    nav = []
    if offset > 0:
        nav.append(B("⬅️", None, f"{CBT.AR_EXCL_PICK_LOT}:{max(0, offset - PAGE_SIZE)}"))
    if offset + PAGE_SIZE < len(all_lots):
        nav.append(B("➡️", None, f"{CBT.AR_EXCL_PICK_LOT}:{offset + PAGE_SIZE}"))
    if nav:
        kb.row(*nav)
    kb.row(B(_("gl_refresh"), None, f"ar_excl_refresh_lots:{offset}"),
           B(_("gl_back"), None, f"{CBT.AR_EXCL_LOTS}:0"))
    return kb


def init_auto_restore_cp(cardinal: Cardinal, *args):
    tg = cardinal.telegram
    bot = tg.bot

    def open_main(c: CallbackQuery):
        bot.edit_message_text(_("desc_ar_excl"), c.message.chat.id, c.message.id, reply_markup=_main_kb())
        bot.answer_callback_query(c.id)

    def open_lots(c: CallbackQuery):
        offset = int(c.data.split(":")[1]) if ":" in c.data else 0
        data = excl.load_exclusions()
        text = _("ar_excl_lots_title") + "\n\n"
        text += _("ar_excl_empty_lots") if not data["lots"] else f"<i>{_('gl_last_update')}: {len(data['lots'])}</i>"
        bot.edit_message_text(text, c.message.chat.id, c.message.id, reply_markup=_lots_kb(offset))
        bot.answer_callback_query(c.id)

    def open_cats(c: CallbackQuery):
        offset = int(c.data.split(":")[1]) if ":" in c.data else 0
        data = excl.load_exclusions()
        text = _("ar_excl_cats_title") + "\n\n"
        text += _("ar_excl_empty_cats") if not data["categories"] else \
            "\n".join(f"• <code>{utils.escape(x)}</code>" for x in data["categories"][:30])
        bot.edit_message_text(text, c.message.chat.id, c.message.id, reply_markup=_cats_kb(offset))
        bot.answer_callback_query(c.id)

    def act_add_lot(c: CallbackQuery):
        msg = bot.send_message(c.message.chat.id, _("ar_excl_enter_lot"), reply_markup=CLEAR_STATE_BTN())
        tg.set_state(c.message.chat.id, msg.id, c.from_user.id, CBT.AR_EXCL_ADD_LOT)
        bot.answer_callback_query(c.id)

    def add_lot_msg(m: Message):
        tg.clear_state(m.chat.id, m.from_user.id, True)
        item_id = (m.text or "").strip()
        if excl.add_lot(item_id):
            bot.reply_to(m, _("ar_excl_lot_added", utils.escape(item_id)), reply_markup=_lots_kb(0))
            logger.info(f"@{m.from_user.username} исключил лот {item_id} из авто-восстановления")
        else:
            bot.reply_to(m, _("ar_excl_lot_exists", utils.escape(item_id)), reply_markup=_lots_kb(0))

    def act_add_cat(c: CallbackQuery):
        msg = bot.send_message(c.message.chat.id, _("ar_excl_enter_cat"), reply_markup=CLEAR_STATE_BTN())
        tg.set_state(c.message.chat.id, msg.id, c.from_user.id, CBT.AR_EXCL_ADD_CAT)
        bot.answer_callback_query(c.id)

    def add_cat_msg(m: Message):
        tg.clear_state(m.chat.id, m.from_user.id, True)
        value = (m.text or "").strip()
        if excl.add_category(value):
            bot.reply_to(m, _("ar_excl_cat_added", utils.escape(value)), reply_markup=_cats_kb(0))
            logger.info(f"@{m.from_user.username} исключил категорию {value} из авто-восстановления")
        else:
            bot.reply_to(m, _("ar_excl_cat_exists", utils.escape(value)), reply_markup=_cats_kb(0))

    def del_lot(c: CallbackQuery):
        parts = c.data.split(":")
        item_id, offset = parts[1], int(parts[2]) if len(parts) > 2 else 0
        excl.remove_lot(item_id)
        bot.answer_callback_query(c.id, _("ar_excl_lot_removed"))
        data = excl.load_exclusions()
        text = _("ar_excl_lots_title") + "\n\n"
        text += _("ar_excl_empty_lots") if not data["lots"] else ""
        bot.edit_message_text(text or _("ar_excl_lots_title"), c.message.chat.id, c.message.id,
                              reply_markup=_lots_kb(offset))

    def del_cat(c: CallbackQuery):
        parts = c.data.split(":")
        index, offset = int(parts[1]), int(parts[2]) if len(parts) > 2 else 0
        data = excl.load_exclusions()
        if 0 <= index < len(data["categories"]):
            excl.remove_category(data["categories"][index])
        bot.answer_callback_query(c.id, _("ar_excl_cat_removed"))
        data = excl.load_exclusions()
        text = _("ar_excl_cats_title") + "\n\n"
        text += _("ar_excl_empty_cats") if not data["categories"] else \
            "\n".join(f"• <code>{utils.escape(x)}</code>" for x in data["categories"][:30])
        bot.edit_message_text(text, c.message.chat.id, c.message.id, reply_markup=_cats_kb(offset))

    def add_stars(c: CallbackQuery):
        if excl.add_category("stars"):
            bot.answer_callback_query(c.id, _("ar_excl_cat_added", "stars"))
        else:
            bot.answer_callback_query(c.id, _("ar_excl_cat_exists", "stars"))
        data = excl.load_exclusions()
        text = _("ar_excl_cats_title") + "\n\n"
        text += "\n".join(f"• <code>{utils.escape(x)}</code>" for x in data["categories"][:30]) or _("ar_excl_empty_cats")
        bot.edit_message_text(text, c.message.chat.id, c.message.id, reply_markup=_cats_kb(0))

    def open_pick(c: CallbackQuery):
        offset = int(c.data.split(":")[1]) if ":" in c.data else 0
        if not getattr(cardinal, "tg_profile", None) or not cardinal.tg_profile.get_common_lots():
            cardinal.update_lots_and_categories()
        bot.edit_message_text(_("ar_excl_pick_title"), c.message.chat.id, c.message.id,
                              reply_markup=_pick_lots_kb(cardinal, offset))
        bot.answer_callback_query(c.id)

    def refresh_pick(c: CallbackQuery):
        offset = int(c.data.split(":")[1]) if ":" in c.data else 0
        cardinal.update_lots_and_categories()
        bot.edit_message_text(_("ar_excl_pick_title"), c.message.chat.id, c.message.id,
                              reply_markup=_pick_lots_kb(cardinal, offset))
        bot.answer_callback_query(c.id, _("gl_refresh"))

    def toggle_pick(c: CallbackQuery):
        parts = c.data.split(":")
        lot_index, list_offset = int(parts[1]), int(parts[2]) if len(parts) > 2 else 0
        lots = cardinal.tg_profile.get_common_lots() if getattr(cardinal, "tg_profile", None) else []
        if lot_index < 0 or lot_index >= len(lots):
            bot.answer_callback_query(c.id, _("gl_error"), show_alert=True)
            return
        item_id = str(lots[lot_index].id)
        if excl.is_lot_excluded(item_id):
            excl.remove_lot(item_id)
            bot.answer_callback_query(c.id, _("ar_excl_lot_removed"))
        else:
            excl.add_lot(item_id)
            bot.answer_callback_query(c.id, _("ar_excl_lot_added", item_id[:12]))
        bot.edit_message_reply_markup(c.message.chat.id, c.message.id,
                                      reply_markup=_pick_lots_kb(cardinal, list_offset))

    tg.cbq_handler(open_main, lambda c: c.data == CBT.AR_EXCL)
    tg.cbq_handler(open_lots, lambda c: c.data.startswith(f"{CBT.AR_EXCL_LOTS}:") or c.data == CBT.AR_EXCL_LOTS)
    tg.cbq_handler(open_cats, lambda c: c.data.startswith(f"{CBT.AR_EXCL_CATS}:") or c.data == CBT.AR_EXCL_CATS)
    tg.cbq_handler(act_add_lot, lambda c: c.data == CBT.AR_EXCL_ADD_LOT)
    tg.cbq_handler(act_add_cat, lambda c: c.data == CBT.AR_EXCL_ADD_CAT)
    tg.cbq_handler(del_lot, lambda c: c.data.startswith(f"{CBT.AR_EXCL_DEL_LOT}:"))
    tg.cbq_handler(del_cat, lambda c: c.data.startswith(f"{CBT.AR_EXCL_DEL_CAT}:"))
    tg.cbq_handler(add_stars, lambda c: c.data == CBT.AR_EXCL_ADD_STARS)
    tg.cbq_handler(open_pick, lambda c: c.data.startswith(f"{CBT.AR_EXCL_PICK_LOT}:"))
    tg.cbq_handler(refresh_pick, lambda c: c.data.startswith("ar_excl_refresh_lots:"))
    tg.cbq_handler(toggle_pick, lambda c: c.data.startswith(f"{CBT.AR_EXCL_TOGGLE_LOT}:"))

    tg.msg_handler(add_lot_msg, func=lambda m: tg.check_state(m.chat.id, m.from_user.id, CBT.AR_EXCL_ADD_LOT))
    tg.msg_handler(add_cat_msg, func=lambda m: tg.check_state(m.chat.id, m.from_user.id, CBT.AR_EXCL_ADD_CAT))


BIND_TO_PRE_INIT = [init_auto_restore_cp]

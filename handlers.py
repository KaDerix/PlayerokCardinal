from __future__ import annotations
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from cardinal import Cardinal

from PlayerokAPI.listener.events import *
from Utils import cardinal_tools
import Utils.exceptions
from locales.localizer import Localizer
import logging
import time
import os
import json
import tempfile
import requests

logger = logging.getLogger("POC.handlers")
localizer = Localizer()
_ = localizer.translate

def log_msg_handler(c: Cardinal, event: NewMessageEvent):
    message = event.message
    chat = event.chat
    chat_name = chat.name if hasattr(chat, 'name') else str(chat.id)
    if hasattr(message, 'user') and message.user:
        author = message.user.username if hasattr(message.user, 'username') else str(message.user.id)
    else:
        author = "Unknown"
    logger.debug(_("log_new_msg", chat_name, chat.id))
    logger.debug(f"$MAGENTA└───> $YELLOW{author}: $CYAN{message.text or ''}")

def send_new_message_notification(c: Cardinal, event: NewMessageEvent):
    if c.telegram is None:
        return
    
    message = event.message
    chat = event.chat
    chat_name = chat.name if hasattr(chat, 'name') else str(chat.id)
    
    if hasattr(c, 'bl_msg_notification_enabled') and c.bl_msg_notification_enabled and chat_name in c.blacklist:
        return
    
    if hasattr(message, 'user') and message.user:
        if hasattr(message.user, 'id') and str(message.user.id) == str(c.account.id):
            return
    
    if message.text:
        mtext = message.text.strip().lower()
        if mtext in c.AR_CFG:
            return

    from tg_bot import utils
    text = utils.format_chat_message_line(
        message, str(c.account.id), c.blacklist, _
    )

    from tg_bot import keyboards
    from tg_bot.utils import NotificationTypes
    kb = keyboards.reply(chat.id, chat_name, extend=True)
    
    from threading import Thread
    Thread(target=c.telegram.send_notification, args=(text, kb, NotificationTypes.new_message),
           daemon=True).start()

def send_response_handler(c: Cardinal, event: NewMessageEvent):
    if not c.autoresponse_enabled:
        return
    
    message = event.message
    chat = event.chat
    
    if not message.text:
        return
    
    mtext = message.text.strip().lower()
    
    if hasattr(message, 'user') and message.user:
        author_username = message.user.username if hasattr(message.user, 'username') else str(message.user.id)
    else:
        author_username = "Unknown"
    
    if hasattr(c, 'bl_response_enabled') and c.bl_response_enabled and author_username in c.blacklist:
        logger.info(f"Пользователь $YELLOW{author_username}$RESET в черном списке, игнорируем.")
        return
    
    if mtext not in c.AR_CFG:
        return
    
    chat_name = chat.name if hasattr(chat, 'name') else str(chat.id)
    logger.info(_("log_new_cmd", mtext, chat_name, chat.id))
    
    command_config = c.AR_CFG[mtext]
    response = command_config.get("response", "")
    if response:
        response = cardinal_tools.format_msg_text(response, message)
        from threading import Thread
        Thread(target=c.send_message, args=(chat.id, response, chat_name), daemon=True).start()

def send_command_notification_handler(c: Cardinal, event: NewMessageEvent):
    if not c.telegram:
        return
    
    message = event.message
    chat = event.chat
    chat_name = chat.name if hasattr(chat, 'name') else str(chat.id)
    
    if hasattr(message, 'user') and message.user:
        author_username = message.user.username if hasattr(message.user, 'username') else str(message.user.id)
    else:
        author_username = "Unknown"
    
    if hasattr(c, 'bl_cmd_notification_enabled') and c.bl_cmd_notification_enabled and author_username in c.blacklist:
        return
    
    command = message.text.strip().lower() if message.text else ""
    if command not in c.AR_CFG:
        return
    
    command_config = c.AR_CFG[command]
    if not command_config.get("telegramNotification", "0") == "1":
        return
    
    from tg_bot import utils, keyboards
    from tg_bot.utils import NotificationTypes
    from threading import Thread
    
    if not command_config.get("notificationText"):
        text = f"🧑‍💻 Пользователь <b><i>{author_username}</i></b> ввел команду <code>{utils.escape(command)}</code>."
    else:
        text = cardinal_tools.format_msg_text(command_config["notificationText"], message)
    
    Thread(target=c.telegram.send_notification, args=(text, keyboards.reply(chat.id, chat_name),
                                                      NotificationTypes.command), daemon=True).start()

def _deal_buyer_username(deal) -> str:
    if hasattr(deal, "user") and deal.user:
        if hasattr(deal.user, "username") and deal.user.username:
            return deal.user.username
        if hasattr(deal.user, "id"):
            return str(deal.user.id)
    return "Unknown"


def _deal_item_name(deal) -> str:
    if hasattr(deal, "item") and deal.item and hasattr(deal.item, "name"):
        return deal.item.name or _("unknown_item")
    return _("unknown_item")


def _deal_price_rub(deal) -> float:
    from Utils.playerok_money import deal_order_price_rub
    return deal_order_price_rub(deal)


def enrich_deal_handler(c: Cardinal, event: NewDealEvent | ItemPaidEvent):
    deal = event.deal
    if not deal or not getattr(deal, "item", None) or not getattr(deal.item, "id", None):
        return
    try:
        from Utils import lots_cache
        lots_cache.upsert(deal.item)
    except Exception:
        pass
    if getattr(deal.item, "name", None) and getattr(deal.item, "category", None):
        return
    try:
        deal.item = c.account.get_item(id=deal.item.id)
        logger.debug(f"Сделка #{deal.id} обогащена данными товара «{getattr(deal.item, 'name', '?')}»")
        try:
            from Utils import lots_cache
            lots_cache.upsert(deal.item)
            lots_cache.save()
        except Exception:
            pass
    except Exception as e:
        logger.debug(f"Не удалось обогатить сделку #{deal.id}: {e}")


_recent_auto_deliveries: dict[str, float] = {}


def new_deal_welcome_handler(c: Cardinal, event: NewDealEvent):
    deal = event.deal
    chat = event.chat
    if not deal or not chat:
        return
    if hasattr(deal, "user") and deal.user and str(deal.user.id) == str(c.account.id):
        return

    greetings_cfg = c.MAIN_CFG.get("Greetings", {})
    if greetings_cfg.get("ignoreSystemMessages", "1") == "1":
        for chat_id in (getattr(c.account, "system_chat_id", None), getattr(c.account, "support_chat_id", None)):
            if chat_id and str(chat.id) == str(chat_id):
                return

    if greetings_cfg.get("sendGreetings", "0") != "1":
        return

    if cardinal_tools.should_skip_deal_greeting(chat.id, greetings_cfg):
        return

    text = greetings_cfg.get("greetingsText", "").strip()
    if not text:
        item_name = _deal_item_name(deal)
        price_rub = _deal_price_rub(deal)
        text = _("new_deal_chat_message", item_name, f"{price_rub:.2f}")
    text = cardinal_tools.format_order_text(text, deal)
    buyer = _deal_buyer_username(deal)
    from threading import Thread
    Thread(target=c.send_message, args=(chat.id, text, buyer), daemon=True).start()
    cardinal_tools.mark_deal_greeting_sent(chat.id)


def deal_confirmed_reply_handler(c: Cardinal, event: DealConfirmedEvent):
    deal = event.deal
    chat = event.chat
    if not deal or not chat:
        return

    oc = c.MAIN_CFG.get("OrderConfirm", {})
    if oc.get("sendReply", "0") != "1":
        return

    text = oc.get("replyText", "").strip()
    if not text:
        return

    text = cardinal_tools.format_order_text(text, deal)
    buyer = _deal_buyer_username(deal)
    watermark = oc.get("watermark", "1") == "1"
    from threading import Thread
    Thread(target=c.send_message, args=(chat.id, text, buyer, watermark), daemon=True).start()


def review_reply_handler(c: Cardinal, event: NewReviewEvent):
    deal = event.deal
    chat = event.chat
    if not deal or not chat:
        return

    rr = c.MAIN_CFG.get("ReviewReply", {})
    if rr.get("sendReply", "0") != "1":
        return

    rating = 0
    if hasattr(deal, "review") and deal.review and hasattr(deal.review, "rating"):
        rating = int(deal.review.rating or 0)
    if rating < 1 or rating > 5:
        return

    text = rr.get(f"reply{rating}", "").strip()
    if not text:
        return

    text = cardinal_tools.format_order_text(text, deal)
    buyer = _deal_buyer_username(deal)
    watermark = rr.get("watermark", "1") == "1"
    from threading import Thread
    Thread(target=c.send_message, args=(chat.id, text, buyer, watermark), daemon=True).start()


def _find_delivery_config(c: Cardinal, lot_id: str | None, item_name: str | None) -> dict | None:
    configs = getattr(c, "AD_CFG", None) or []
    if lot_id:
        for config in configs:
            if str(config.get("lot_id") or "") == str(lot_id):
                return config
    name = (item_name or "").strip().lower()
    if name:
        for config in configs:
            if str(config.get("name") or "").strip().lower() == name:
                return config
    return None


def _sync_ad_lot_id(c: Cardinal, section_name: str, new_lot_id: str) -> None:
    if not section_name or not new_lot_id:
        return
    try:
        from Utils import ad_config as adc
        raw = c.RAW_AD_CFG
        if not raw.has_section(section_name):
            return
        old = raw[section_name].get("lot_id", "").strip()
        if old == str(new_lot_id):
            return
        raw.set(section_name, "lot_id", str(new_lot_id))
        adc.save_ad_cfg(c)
        logger.info(f"Автовыдача «{section_name}»: lot_id обновлён {old or '—'} → {new_lot_id}")
    except Exception as e:
        logger.debug(f"sync ad lot_id: {e}")


def auto_delivery_handler(c: Cardinal, event: NewDealEvent | ItemPaidEvent):
    if not c.autodelivery_enabled:
        return

    deal = event.deal
    chat = event.chat
    if not deal or not chat:
        return

    now = time.time()
    if deal.id in _recent_auto_deliveries and now - _recent_auto_deliveries[deal.id] < 60:
        logger.debug(f"Автовыдача для сделки #{deal.id} уже выполнялась — пропуск")
        return
    _recent_auto_deliveries[deal.id] = now

    logger.info(f"Обработка заказа $YELLOW#{deal.id}$RESET")

    lot_id = None
    item_name = ""
    if hasattr(deal, "item") and deal.item:
        lot_id = str(getattr(deal.item, "id", None) or getattr(deal.item, "lot_id", None) or "") or None
        item_name = getattr(deal.item, "name", None) or ""

    delivery_config = _find_delivery_config(c, lot_id, item_name)
    if not delivery_config:
        logger.debug(f"Конфигурация автовыдачи для лота $YELLOW{lot_id or item_name}$RESET не найдена")
        return

    if delivery_config.get("disable") in ("1", 1, True, "true"):
        logger.info(f"Автовыдача отключена для лота $YELLOW{delivery_config.get('name') or lot_id}$RESET")
        return

    cfg_name = delivery_config.get("name") or ""
    if lot_id and cfg_name and str(delivery_config.get("lot_id") or "") != str(lot_id):
        _sync_ad_lot_id(c, cfg_name, lot_id)
        delivery_config["lot_id"] = str(lot_id)

    logger.info(
        f"Найдена конфигурация автовыдачи для лота $YELLOW{cfg_name or lot_id}$RESET"
        f"{' (лимитированная)' if delivery_config.get('goods_file') else ''}"
    )

    goods_file = delivery_config.get("goods_file")
    response = delivery_config.get("response", "")
    products: list[str] = []
    goods_left = -1

    if goods_file:
        amount = 1
        if c.multidelivery_enabled and delivery_config.get("disableMultiDelivery") not in ("1", True):
            amount = cardinal_tools.parse_delivery_amount_from_name(item_name, 1)

        try:
            result = cardinal_tools.get_products(goods_file, amount)
            if result is None:
                logger.error(f"Файл $YELLOW{goods_file}$RESET пуст или произошла ошибка при чтении!")
                return
            products, goods_left = result
        except Utils.exceptions.NoProductsError:
            logger.error(f"В файле $YELLOW{goods_file}$RESET нет товаров!")
            return
        except Utils.exceptions.NotEnoughProductsError as e:
            logger.error(f"В файле $YELLOW{goods_file}$RESET недостаточно товаров: {e}")
            return
        except Exception as e:
            logger.error(
                f"Произошла ошибка при получении товаров для заказа $YELLOW#{deal.id}$RESET: $YELLOW{e}$RESET"
            )
            logger.debug("TRACEBACK", exc_info=True)
            return

    delivery_text = cardinal_tools.format_order_text(response, deal)
    if goods_file:
        delivery_text = delivery_text.replace("$product", "\n".join(products).replace("\\n", "\n"))
    else:
        delivery_text = delivery_text.replace("$product", "")

    buyer_name = (
        deal.user.username if hasattr(deal, "user") and deal.user and hasattr(deal.user, "username")
        else str(deal.user.id) if hasattr(deal, "user") and deal.user else "Unknown"
    )
    sent = c.send_message(chat.id, delivery_text, buyer_name)

    if not sent:
        logger.error(f"Не удалось отправить товар для ордера $YELLOW#{deal.id}$RESET.")
        if goods_file and products:
            cardinal_tools.add_products(goods_file, products, at_zero_position=True)
        if c.telegram:
            from tg_bot.utils import NotificationTypes
            from threading import Thread
            error_text = f"❌ <code>Не удалось отправить товар для ордера {deal.id}.</code>"
            Thread(
                target=c.telegram.send_notification,
                args=(error_text, None, NotificationTypes.delivery),
                daemon=True,
            ).start()
        return

    given = ", ".join(products) if products else delivery_text[:80]
    logger.info(f"Товар для заказа $YELLOW#{deal.id}$RESET выдан: $CYAN{given}$RESET")

    try:
        from PlayerokAPI.enums import ItemDealStatuses
        time.sleep(0.5)
        c.account.update_deal(str(deal.id), ItemDealStatuses.SENT)
        logger.info(f"Сделка $YELLOW#{deal.id}$RESET подтверждена (SENT) после автовыдачи")
    except Exception as e:
        logger.warning(f"Не удалось подтвердить сделку #{deal.id} после выдачи: {e}")

    if c.telegram:
        from tg_bot import utils
        from tg_bot.utils import NotificationTypes
        from threading import Thread
        left = "<b>∞</b>" if goods_left == -1 else f"<code>{goods_left}</code>"
        text = f"""✅ Успешно выдал товар для ордера <code>{deal.id}</code>.\n
🛒 <b><i>Товар:</i></b>
<code>{utils.escape(delivery_text)}</code>\n
📋 <b><i>Осталось товаров: </i></b>{left}"""
        Thread(
            target=c.telegram.send_notification,
            args=(text, None, NotificationTypes.delivery),
            daemon=True,
        ).start()
    from Utils import playerok_automation
    playerok_automation.process_auto_disable_for_lot(c, lot_id or delivery_config.get("lot_id"), delivery_config)

def chat_initialized_handler(c: Cardinal, event: ChatInitializedEvent):
    from Utils import lots_cache
    started = lots_cache.start_watch_loop(c)
    if not started:
        return

    def _once():
        time.sleep(6)
        try:
            _catchup_auto_restore(c)
        except Exception as e:
            logger.debug(f"catchup restore: {e}")

    from threading import Thread
    Thread(target=_once, daemon=True).start()


def _pick_priority_status_id(c: Cardinal, item_id: str, item_price) -> tuple[str, str | None]:
    status_free_id = "1efbe5bc-99a7-68e5-4534-85dad913b981"
    if isinstance(c.MAIN_CFG, dict):
        restore_mode = c.MAIN_CFG.get("Playerok", {}).get("restorePriorityMode", "free")
    else:
        restore_mode = c.MAIN_CFG.get("Playerok", "restorePriorityMode", fallback="free")

    status_premium_id = None
    price_premium = None
    balance = 0.0
    try:
        bal = c.get_balance()
        balance = float(getattr(bal, "available", 0) or 0) if bal else 0.0
    except Exception:
        pass
    try:
        price_s = str(item_price if item_price is not None else "0")
        for ps in c.account.get_item_priority_statuses(item_id, price_s) or []:
            sp = getattr(ps, "price", 0) or 0
            if sp > 0 and (price_premium is None or sp < price_premium):
                price_premium = sp
                status_premium_id = getattr(ps, "id", None)
    except Exception as e:
        logger.debug(f"priority statuses {item_id}: {e}")

    if restore_mode == "premium" and status_premium_id and price_premium is not None and balance >= float(price_premium):
        return status_premium_id, status_premium_id
    return status_free_id, status_premium_id


def _find_item_for_restore(c: Cardinal, item_id: str):
    from PlayerokAPI.enums import ItemStatuses
    from Utils import lots_cache

    try:
        item = c.account.get_item(id=item_id)
        if item:
            lots_cache.upsert(item)
            return item
    except Exception as e:
        logger.debug(f"get_item {item_id}: {e}")

    for statuses in (
        [ItemStatuses.SOLD],
        [ItemStatuses.DRAFT, ItemStatuses.EXPIRED],
        [ItemStatuses.APPROVED, ItemStatuses.PENDING_APPROVAL, ItemStatuses.PENDING_MODERATION],
    ):
        cursor = None
        for _ in range(8):
            try:
                page = c.account.get_my_items(statuses=statuses, count=24, after_cursor=cursor)
            except Exception as e:
                logger.debug(f"get_my_items restore scan: {e}")
                break
            for it in getattr(page, "items", None) or []:
                if str(getattr(it, "id", "")) == str(item_id):
                    lots_cache.upsert(it)
                    try:
                        full = c.account.get_item(id=item_id)
                        if full:
                            lots_cache.upsert(full)
                            return full
                    except Exception:
                        return it
                    return it
            info = getattr(page, "page_info", None)
            if not info or not getattr(info, "has_next_page", False):
                break
            cursor = getattr(info, "end_cursor", None)
            if not cursor:
                break

    return lots_cache.as_item(item_id)


def _restore_item_by_id(
    c: Cardinal,
    item_id: str,
    *,
    retries: int = 5,
    delay: float = 1.2,
    item_name: str | None = None,
    deal_item=None,
) -> bool:
    if not c.autorestore_enabled or not item_id:
        return False

    from Utils import lots_cache
    from Utils.item_restore import restore_after_sale

    item_id = str(item_id)
    snap = lots_cache.get(item_id)
    name = (item_name or (snap or {}).get("name") or getattr(deal_item, "name", None) or item_id)

    probe = deal_item or lots_cache.as_item(item_id)
    skip = _restore_skip_reason(c, probe) if probe else None
    if skip:
        logger.info(f"Авто-восстановление пропуск ({item_id}): {skip}")
        _dequeue_pending_restore(item_id)
        return False

    ok = restore_after_sale(
        c,
        item_id=item_id,
        item_name=str(name),
        deal_item=deal_item,
    )
    if ok:
        _dequeue_pending_restore(item_id)
    return ok


def _catchup_auto_restore(c: Cardinal) -> None:
    if not c.autorestore_enabled:
        return
    _save_pending_restore_items([])

    time.sleep(2)
    pending: list[tuple[str, str, Any]] = []
    seen: set[str] = set()
    try:
        from PlayerokAPI.enums import ItemDealStatuses, ItemDealDirections
        from datetime import datetime, timezone, timedelta

        deals_page = c.account.get_deals(
            statuses=[ItemDealStatuses.PAID, ItemDealStatuses.SENT, ItemDealStatuses.PENDING],
            direction=ItemDealDirections.OUT,
            count=24,
        )
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=15)
        for deal in getattr(deals_page, "deals", None) or []:
            created = getattr(deal, "created_at", None)
            if created:
                try:
                    raw = str(created).replace("Z", "+00:00")
                    dt = datetime.fromisoformat(raw)
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    if dt < cutoff:
                        continue
                except Exception:
                    pass
            item = getattr(deal, "item", None)
            iid = str(getattr(item, "id", "") or "")
            if iid and iid not in seen:
                seen.add(iid)
                pending.append((iid, getattr(item, "name", None) or iid, item))
    except Exception as e:
        logger.debug(f"Catchup get_deals: {e}")

    if not pending:
        return
    logger.info(f"🔄 Catchup: свежие продажи за 15 мин — {len(pending)} лот(ов)")
    for item_id, item_name, deal_item in pending:
        try:
            _restore_item_by_id(c, item_id, item_name=item_name, deal_item=deal_item)
        except Exception as e:
            logger.warning(f"Catchup restore {item_id}: {e}")
        time.sleep(3.0)


def create_deal_keyboard(chat_id: str, username: str, deal_id: str, deal=None):
    from tg_bot import keyboards as kb
    status = getattr(deal, "status", None) if deal is not None else None
    return kb.new_order(deal_id, username, chat_id, deal_status=status)

_recent_order_notices: dict[str, float] = {}


def send_new_deal_notification(c: Cardinal, event: NewDealEvent):
    if not c.telegram:
        return
    
    deal = event.deal
    chat = event.chat
    if not deal or not getattr(deal, "id", None):
        return

    now = time.time()
    last = _recent_order_notices.get(deal.id)
    if last is not None and now - last < 120:
        return
    _recent_order_notices[deal.id] = now
    if len(_recent_order_notices) > 500:
        cutoff = now - 3600
        for k in [k for k, t in _recent_order_notices.items() if t < cutoff]:
            _recent_order_notices.pop(k, None)
    
    buyer_username = _deal_buyer_username(deal)
    
    if buyer_username in c.blacklist and hasattr(c.MAIN_CFG, 'get') and isinstance(c.MAIN_CFG.get("BlockList"), dict) and c.MAIN_CFG.get("BlockList", {}).get("blockNewOrderNotification") == "1":
        return
    
    item_name = _deal_item_name(deal)
    subcategory_name = ""
    if hasattr(deal, 'item') and deal.item and hasattr(deal.item, 'category') and deal.item.category:
        subcategory_name = deal.item.category.name if hasattr(deal.item.category, 'name') else ""
    
    price_rub = _deal_price_rub(deal)

    lot_id = None
    if hasattr(deal, "item") and deal.item and getattr(deal.item, "id", None):
        lot_id = str(deal.item.id)

    delivery_config = _find_delivery_config(
        c,
        lot_id,
        item_name if item_name != "Unknown" else None,
    )

    if not delivery_config:
        delivery_info = _("ntfc_new_order_not_in_cfg")
    elif delivery_config.get("disable") in ("1", 1, True, "true"):
        delivery_info = _("ntfc_new_order_ad_disabled_for_lot")
    elif not c.autodelivery_enabled:
        delivery_info = _("ntfc_new_order_ad_disabled")
    else:
        delivery_info = _("ntfc_new_order_will_be_delivered")
    
    from tg_bot import utils
    description = f"{utils.escape(item_name)}"
    if subcategory_name:
        description += f", {utils.escape(subcategory_name)}"
    
    text = _("ntfc_new_order", description, buyer_username, f"{price_rub:.2f} RUB", deal.id, delivery_info)
    
    keyboard = create_deal_keyboard(str(chat.id), buyer_username, deal.id, deal)

    logger.info(_("log_new_order", item_name, f"{price_rub:.2f}", buyer_username))
    
    from tg_bot.utils import NotificationTypes
    from threading import Thread
    Thread(target=c.telegram.send_notification, args=(text, keyboard, NotificationTypes.new_order),
           daemon=True).start()


def send_item_sent_notification(c: Cardinal, event: ItemSentEvent):
    if c.telegram is None:
        return
    deal = event.deal
    chat = event.chat
    buyer_username = _deal_buyer_username(deal)
    item_name = _deal_item_name(deal)
    text = _("ntfc_item_sent", buyer_username, item_name, deal.id)
    keyboard = create_deal_keyboard(str(chat.id), buyer_username, deal.id, deal)
    logger.info(_("log_order_sent", deal.id))
    from tg_bot.utils import NotificationTypes
    from threading import Thread
    Thread(target=c.telegram.send_notification, args=(text, keyboard, NotificationTypes.order_confirmed),
           daemon=True).start()

def send_deal_confirmed_notification(c: Cardinal, event: DealConfirmedEvent):
    if c.telegram is None:
        return
    deal = event.deal
    chat = event.chat
    buyer_username = _deal_buyer_username(deal)
    item_name = _deal_item_name(deal)
    text = _("ntfc_deal_confirmed", buyer_username, item_name, deal.id)
    keyboard = create_deal_keyboard(str(chat.id), buyer_username, deal.id, deal)
    logger.info(_("log_order_confirmed", deal.id))
    from tg_bot.utils import NotificationTypes
    from threading import Thread
    Thread(target=c.telegram.send_notification, args=(text, keyboard, NotificationTypes.order_confirmed),
           daemon=True).start()

def send_deal_rolled_back_notification(c: Cardinal, event: DealRolledBackEvent):
    if c.telegram is None:
        return
    deal = event.deal
    chat = event.chat
    buyer_username = _deal_buyer_username(deal)
    item_name = _deal_item_name(deal)
    text = _("ntfc_deal_rolled_back", buyer_username, item_name, deal.id)
    keyboard = create_deal_keyboard(str(chat.id), buyer_username, deal.id, deal)
    from tg_bot.utils import NotificationTypes
    from threading import Thread
    Thread(target=c.telegram.send_notification, args=(text, keyboard, NotificationTypes.order_confirmed),
           daemon=True).start()

_recent_review_notices: dict[str, float] = {}


def send_new_review_notification(c: Cardinal, event: NewReviewEvent):
    if c.telegram is None:
        return

    deal = event.deal
    chat = event.chat
    if not deal or not getattr(deal, "id", None):
        return

    now = time.time()
    last = _recent_review_notices.get(deal.id)
    if last is not None and now - last < 600:
        return
    _recent_review_notices[deal.id] = now
    if len(_recent_review_notices) > 500:
        cutoff = now - 3600
        for k in [k for k, t in _recent_review_notices.items() if t < cutoff]:
            _recent_review_notices.pop(k, None)

    buyer_username = deal.user.username if hasattr(deal, 'user') and hasattr(deal.user, 'username') else str(deal.user.id) if hasattr(deal, 'user') and deal.user else "Unknown"

    review_text = ""
    review_rating = 0
    if hasattr(deal, 'review') and deal.review:
        if hasattr(deal.review, 'text'):
            review_text = deal.review.text
        if hasattr(deal.review, 'rating'):
            review_rating = deal.review.rating

    stars = "⭐" * review_rating if review_rating else ""

    from tg_bot import utils

    keyboard = create_deal_keyboard(str(chat.id) if chat else "", buyer_username, deal.id, deal)

    from tg_bot.utils import NotificationTypes
    from threading import Thread
    Thread(target=c.telegram.send_notification,
           args=(_("ntfc_new_review").format(stars, deal.id, utils.escape(review_text or "")),
                 keyboard, NotificationTypes.review),
           daemon=True).start()

def send_deal_has_problem_notification(c: Cardinal, event: DealHasProblemEvent):
    if c.telegram is None:
        return
    
    deal = event.deal
    chat = event.chat
    
    buyer_username = deal.user.username if hasattr(deal, 'user') and hasattr(deal.user, 'username') else str(deal.user.id) if hasattr(deal, 'user') and deal.user else "Unknown"
    item_name = deal.item.name if hasattr(deal, 'item') and hasattr(deal.item, 'name') else "Неизвестный товар"
    
    notification_text = f"⚠️ <b>Проблема в сделке!</b>\n\n"
    notification_text += f"👤 <b>Покупатель:</b> {buyer_username}\n"
    notification_text += f"📦 <b>Товар:</b> {item_name}\n"
    notification_text += f"🆔 <b>ID сделки:</b> <code>{deal.id}</code>"
    
    keyboard = create_deal_keyboard(str(chat.id), buyer_username, deal.id, deal)
    
    from tg_bot.utils import NotificationTypes
    from threading import Thread
    Thread(target=c.telegram.send_notification, args=(notification_text, keyboard, NotificationTypes.deal_problem),
           daemon=True).start()

def send_deal_problem_resolved_notification(c: Cardinal, event: DealProblemResolvedEvent):
    if c.telegram is None:
        return
    
    deal = event.deal
    chat = event.chat
    
    buyer_username = deal.user.username if hasattr(deal, 'user') and hasattr(deal.user, 'username') else str(deal.user.id) if hasattr(deal, 'user') and deal.user else "Unknown"
    item_name = deal.item.name if hasattr(deal, 'item') and hasattr(deal.item, 'name') else "Неизвестный товар"
    
    notification_text = f"✅ <b>Проблема решена!</b>\n\n"
    notification_text += f"👤 <b>Покупатель:</b> {buyer_username}\n"
    notification_text += f"📦 <b>Товар:</b> {item_name}\n"
    notification_text += f"🆔 <b>ID сделки:</b> <code>{deal.id}</code>"
    
    keyboard = create_deal_keyboard(str(chat.id), buyer_username, deal.id, deal)
    
    from tg_bot.utils import NotificationTypes
    from threading import Thread
    Thread(target=c.telegram.send_notification, args=(notification_text, keyboard, NotificationTypes.deal_problem),
           daemon=True).start()

def _deal_status_label(status) -> str:
    labels = {
        "PAID": _("deal_status_paid"),
        "PENDING": _("deal_status_pending"),
        "SENT": _("deal_status_sent"),
        "CONFIRMED": _("deal_status_confirmed"),
        "ROLLED_BACK": _("deal_status_rolled_back"),
    }
    if status and hasattr(status, "name"):
        return labels.get(status.name, status.name)
    return _("deal_status_unknown")


def send_deal_status_changed_notification(c: Cardinal, event: DealStatusChangedEvent):
    if c.telegram is None:
        return
    deal = event.deal
    chat = event.chat
    buyer_username = _deal_buyer_username(deal)
    status_text = _deal_status_label(getattr(deal, "status", None))
    text = _("ntfc_deal_status_changed", deal.id, status_text, buyer_username)
    keyboard = create_deal_keyboard(str(chat.id), buyer_username, deal.id, deal)
    from tg_bot.utils import NotificationTypes
    from threading import Thread
    Thread(target=c.telegram.send_notification, args=(text, keyboard, NotificationTypes.order_confirmed),
           daemon=True).start()

def _plugin_by_filename(c: Cardinal, filename: str):
    needle = filename.lower().replace("\\", "/")
    for plugin in (getattr(c, "plugins", None) or {}).values():
        path = (getattr(plugin, "path", None) or "").replace("\\", "/").lower()
        if path.endswith(needle) or path.endswith("/" + needle):
            return plugin
    return None


def _is_telegram_stars_category(item) -> bool:
    cat = getattr(item, "category", None)
    if not cat:
        return False
    slug = (getattr(cat, "slug", None) or "").strip().lower()
    if slug == "stars":
        return True
    name = (getattr(cat, "name", None) or "").strip().lower().replace("ё", "е")
    return name in {"stars", "звезды", "telegram stars", "tg stars"}


def _is_stars_category_item(item) -> bool:
    return _is_telegram_stars_category(item)


def _is_steam_rent_managed_item(item) -> bool:
    if not item or not getattr(item, "id", None):
        return False
    lots_path = os.path.join("storage", "plugins", "auto_steam_rent", "lots.json")
    if not os.path.exists(lots_path):
        return False
    try:
        with open(lots_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        item_id = str(item.id)
        for lot in data.get("lots", []):
            ref = str(lot.get("item_id") or lot.get("lot_id") or "")
            if ref and ref == item_id:
                return True
    except Exception:
        return False
    return False


def _ad_restore_disabled(c: Cardinal, item_id: str) -> bool:
    for cfg in getattr(c, "AD_CFG", None) or []:
        if str(cfg.get("lot_id") or "") == str(item_id):
            return cfg.get("disableAutoRestore") in ("1", 1, True, "true")
    return False


def _restore_skip_reason(c: Cardinal, item) -> str | None:
    if not item:
        return "нет товара"
    item_id = str(getattr(item, "id", "") or "")

    if item_id and _ad_restore_disabled(c, item_id):
        return f"disableAutoRestore в автовыдаче ({item_id})"

    try:
        from Utils.auto_restore_exclusions import exclusion_reason_for_item
        reason = exclusion_reason_for_item(item)
        if reason:
            return reason
    except Exception as e:
        logger.debug(f"exclusions check failed: {e}")

    if _is_steam_rent_managed_item(item):
        steam = _plugin_by_filename(c, "auto_steam_rent.py")
        if steam is not None and getattr(steam, "enabled", False):
            return "лот привязан к auto_steam_rent"

    if _is_telegram_stars_category(item):
        stars = _plugin_by_filename(c, "fast_stars.py")
        if stars is not None and getattr(stars, "enabled", False):
            return "категория Stars + включён fast_stars"

    return None


_PENDING_RESTORE_PATH = os.path.join("storage", "cache", "pending_restore_items.json")
_recent_auto_restores: dict[str, float] = {}


def _load_pending_restore_items() -> list[str]:
    try:
        if not os.path.exists(_PENDING_RESTORE_PATH):
            return []
        with open(_PENDING_RESTORE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return [str(x) for x in data if x]
        if isinstance(data, dict):
            return [str(x) for x in data.get("items", []) if x]
    except Exception:
        pass
    return []


def _save_pending_restore_items(items: list[str]) -> None:
    try:
        os.makedirs(os.path.dirname(_PENDING_RESTORE_PATH), exist_ok=True)
        seen = set()
        uniq = []
        for i in items:
            if i not in seen:
                seen.add(i)
                uniq.append(i)
        with open(_PENDING_RESTORE_PATH, "w", encoding="utf-8") as f:
            json.dump({"items": uniq}, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.warning(f"Не удалось сохранить очередь восстановления: {e}")


def _queue_pending_restore(item_id: str) -> None:
    items = _load_pending_restore_items()
    if item_id not in items:
        items.append(item_id)
        _save_pending_restore_items(items)


def _dequeue_pending_restore(item_id: str) -> None:
    items = [i for i in _load_pending_restore_items() if i != item_id]
    _save_pending_restore_items(items)


def _item_can_publish(item_details) -> bool:
    from PlayerokAPI.enums import ItemStatuses
    st = getattr(item_details, "status", None)
    if st == ItemStatuses.APPROVED:
        return False
    may_pub = getattr(item_details, "may_be_published", None)
    if may_pub is True:
        return True
    if getattr(item_details, "is_editable", False):
        return True
    if st in (ItemStatuses.DRAFT, ItemStatuses.SOLD, ItemStatuses.EXPIRED, ItemStatuses.PENDING_APPROVAL):
        return True
    return may_pub is not False


def auto_restore_handler(c: Cardinal, event: NewDealEvent | ItemPaidEvent | ItemSentEvent | DealRolledBackEvent):
    if not c.autorestore_enabled:
        logger.info("Авто-восстановление пропуск: autoRestore выключен в конфиге")
        return
    
    deal = event.deal
    if not deal or not getattr(deal, "item", None) or not getattr(deal.item, "id", None):
        logger.info("Авто-восстановление пропуск: в событии нет deal.item.id")
        return

    deal_id = str(deal.id)
    item_id = str(deal.item.id)
    item_name = getattr(deal.item, "name", None) or item_id

    now = time.time()
    last_deal = _recent_auto_restores.get(f"deal:{deal_id}")
    if last_deal is not None and now - last_deal < 120:
        return
    _recent_auto_restores[f"deal:{deal_id}"] = now

    from Utils import lots_cache
    lots_cache.upsert(deal.item)

    check_item = deal.item
    if not getattr(check_item, "category", None):
        cached = lots_cache.as_item(item_id)
        if cached and getattr(cached, "category", None):
            check_item = cached

    skip = _restore_skip_reason(c, check_item)
    if skip:
        logger.info(f"Авто-восстановление пропуск «{item_name}»: {skip}")
        return

    last = _recent_auto_restores.get(item_id)
    if last is not None and now - last < 30:
        return
    _recent_auto_restores[item_id] = now
    if len(_recent_auto_restores) > 800:
        cutoff = now - 600
        for k in [k for k, t in _recent_auto_restores.items() if t < cutoff]:
            _recent_auto_restores.pop(k, None)

    _queue_pending_restore(item_id)
    logger.info(f"🚀 Запуск авто-восстановления для товара {item_name} (ID: {item_id})")

    from threading import Thread
    Thread(
        target=_restore_item_by_id,
        args=(c, item_id),
        kwargs={"item_name": item_name, "deal_item": deal.item},
        daemon=True,
    ).start()


def send_bot_started_notification_handler(c: Cardinal, *args):
    if c.telegram is None:
        return
    balance = c.balance
    if balance is None:
        balance = c.get_balance()
    
    active_sales = 0
    try:
        if hasattr(c.account, 'profile') and c.account.profile and hasattr(c.account.profile, 'stats'):
            if hasattr(c.account.profile.stats, 'deals') and c.account.profile.stats.deals:
                if hasattr(c.account.profile.stats.deals, 'incoming') and c.account.profile.stats.deals.incoming:
                    active_sales = getattr(c.account.profile.stats.deals.incoming, 'total', 0)
    except:
        pass
    
    balance_rub = balance.value if balance.value else 0
    balance_usd = 0.0
    balance_eur = 0.0
    
    text = _("poc_init", c.VERSION, c.account.username, c.account.id,
             balance_rub, balance_usd, balance_eur, active_sales)
    if os.getenv("POC_IS_RUNNING_AS_SERVICE", "0") == "1":
        import getpass
        text += _("poc_init_service_hint", getpass.getuser())
    for i in c.telegram.init_messages:
        try:
            c.telegram.bot.edit_message_text(text, i[0], i[1])
        except:
            continue


def register_handlers(c: Cardinal):
    if hasattr(c, 'handler_bind_var_names'):
        import handlers as handlers_module
        for var_name, handler_list in c.handler_bind_var_names.items():
            if hasattr(handlers_module, var_name):
                bind_list = getattr(handlers_module, var_name)
                handler_list.extend(bind_list)
    
    c.chat_initialized_handlers.append(chat_initialized_handler)
    c.new_message_handlers.append(log_msg_handler)
    c.new_message_handlers.append(send_new_message_notification)
    c.new_message_handlers.append(send_response_handler)
    c.new_message_handlers.append(send_command_notification_handler)
    
    c.new_deal_handlers.append(enrich_deal_handler)
    c.new_deal_handlers.append(send_new_deal_notification)
    c.new_deal_handlers.append(new_deal_welcome_handler)
    c.new_deal_handlers.append(auto_restore_handler)
    c.new_deal_handlers.append(auto_delivery_handler)

    from Utils import playerok_automation
    c.new_deal_handlers.append(playerok_automation.try_auto_complete_deal)
    
    c.item_paid_handlers.append(enrich_deal_handler)
    c.item_paid_handlers.append(auto_restore_handler)
    
    c.item_sent_handlers.append(send_item_sent_notification)
    c.deal_confirmed_handlers.append(deal_confirmed_reply_handler)
    c.deal_confirmed_handlers.append(send_deal_confirmed_notification)
    c.deal_rolled_back_handlers.append(send_deal_rolled_back_notification)
    c.deal_rolled_back_handlers.append(auto_restore_handler)
    c.new_review_handlers.append(review_reply_handler)
    c.new_review_handlers.append(send_new_review_notification)
    c.deal_has_problem_handlers.append(send_deal_has_problem_notification)
    c.deal_problem_resolved_handlers.append(send_deal_problem_resolved_notification)
    c.deal_status_changed_handlers.append(send_deal_status_changed_notification)


BIND_TO_POST_INIT = [send_bot_started_notification_handler]

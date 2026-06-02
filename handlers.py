from __future__ import annotations
from typing import TYPE_CHECKING

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
    logger.info(_("log_new_msg", chat_name, chat.id))
    logger.info(f"$MAGENTA└───> $YELLOW{author}: $CYAN{message.text or ''}")

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
    
    if hasattr(message, 'user') and message.user:
        author_username = message.user.username if hasattr(message.user, 'username') else str(message.user.id)
        author_id = str(message.user.id) if hasattr(message.user, 'id') else ""
    else:
        author_username = "Unknown"
        author_id = ""
    
    text = ""
    if author_id == str(c.account.id):
        author = f"<i><b>🫵 {_('you')}:</b></i> "
    elif author_username in c.blacklist:
        author = f"<i><b>🚷 {author_username}: </b></i>"
    else:
        author = f"<i><b>👤 {author_username}: </b></i>"
    
    from tg_bot import utils
    msg_text = f"<code>{utils.escape(message.text)}</code>" if message.text else \
        f"<a href=\"{message.file.url if hasattr(message, 'file') and message.file and hasattr(message.file, 'url') else '#'}\">" \
        f"{_('photo')}</a>" if hasattr(message, 'file') and message.file else "[Медиа]"
    
    text = f"{author}{msg_text}\n\n"
    
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
    if hasattr(deal, "item") and deal.item and hasattr(deal.item, "price"):
        price = deal.item.price or 0
        return price / 100 if price else 0
    return 0


def enrich_deal_handler(c: Cardinal, event: NewDealEvent | ItemPaidEvent):
    deal = event.deal
    if not deal or not getattr(deal, "item", None) or not getattr(deal.item, "id", None):
        return
    if getattr(deal.item, "name", None) and getattr(deal.item, "category", None):
        return
    try:
        deal.item = c.account.get_item(id=deal.item.id)
        logger.debug(f"Сделка #{deal.id} обогащена данными товара «{getattr(deal.item, 'name', '?')}»")
    except Exception as e:
        logger.warning(f"Не удалось обогатить сделку #{deal.id}: {e}")


_recent_auto_deliveries: dict[str, float] = {}


def new_deal_welcome_handler(c: Cardinal, event: NewDealEvent):
    deal = event.deal
    chat = event.chat
    if not deal or not chat:
        return
    if hasattr(deal, "user") and deal.user and str(deal.user.id) == str(c.account.id):
        return
    for chat_id in (getattr(c.account, "system_chat_id", None), getattr(c.account, "support_chat_id", None)):
        if chat_id and str(chat.id) == str(chat_id):
            return

    greetings_cfg = c.MAIN_CFG.get("Greetings", {}) if hasattr(c.MAIN_CFG, "get") else {}
    if isinstance(greetings_cfg, dict) and greetings_cfg.get("sendNewDealMessage", "0") != "1":
        return

    item_name = _deal_item_name(deal)
    price_rub = _deal_price_rub(deal)
    text = _("new_deal_chat_message", item_name, f"{price_rub:.2f}")
    text = cardinal_tools.format_order_text(text, deal)
    buyer = _deal_buyer_username(deal)
    from threading import Thread
    Thread(target=c.send_message, args=(chat.id, text, buyer), daemon=True).start()


def auto_delivery_handler(c: Cardinal, event: NewDealEvent | ItemPaidEvent):
    if not c.autodelivery_enabled:
        return
    
    deal = event.deal
    chat = event.chat

    now = time.time()
    if deal.id in _recent_auto_deliveries and now - _recent_auto_deliveries[deal.id] < 60:
        logger.debug(f"Автовыдача для сделки #{deal.id} уже выполнялась — пропуск")
        return
    _recent_auto_deliveries[deal.id] = now
    
    logger.info(f"Обработка заказа $YELLOW#{deal.id}$RESET")
    
    lot_id = None
    if hasattr(deal, 'item') and deal.item:
        if hasattr(deal.item, 'id'):
            lot_id = str(deal.item.id)
        elif hasattr(deal.item, 'lot_id'):
            lot_id = str(deal.item.lot_id)
    
    if not lot_id:
        logger.warning(f"Не удалось определить lot_id для заказа $YELLOW#{deal.id}$RESET")
        return
    
    delivery_config = None
    for config in c.AD_CFG:
        if config.get("lot_id") == lot_id:
            delivery_config = config
            break
    
    if not delivery_config:
        logger.debug(f"Конфигурация автовыдачи для лота $YELLOW{lot_id}$RESET не найдена")
        return
    
    logger.info(f"Найдена конфигурация автовыдачи для лота $YELLOW{lot_id}$RESET")
    
    goods_file = delivery_config.get("goods_file")
    response = delivery_config.get("response", "")
    
    if not goods_file:
        logger.error(f"Не указан файл товаров для лота $YELLOW{lot_id}$RESET")
        return
    
    amount = 1
    if c.multidelivery_enabled and delivery_config.get("disableMultiDelivery") not in ("1", True):
        item_name = deal.item.name if hasattr(deal, "item") and deal.item else ""
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
        logger.error(f"Произошла ошибка при получении товаров для заказа $YELLOW#{deal.id}$RESET: $YELLOW{e}$RESET")
        logger.debug("TRACEBACK", exc_info=True)
        return
    
    delivery_text = cardinal_tools.format_order_text(response, deal)
    delivery_text = delivery_text.replace("$product", "\n".join(products).replace("\\n", "\n"))
    
    buyer_name = deal.user.username if hasattr(deal, 'user') and hasattr(deal.user, 'username') else str(deal.user.id) if hasattr(deal, 'user') and deal.user else "Unknown"
    result = c.send_message(chat.id, delivery_text, buyer_name)
    
    if not result:
        logger.error(f"Не удалось отправить товар для ордера $YELLOW#{deal.id}$RESET.")
        if products:
            cardinal_tools.add_products(goods_file, products, at_zero_position=True)
        if c.telegram:
            from tg_bot.utils import NotificationTypes
            from threading import Thread
            error_text = f"❌ <code>Не удалось отправить товар для ордера {deal.id}.</code>"
            Thread(target=c.telegram.send_notification, args=(error_text, None, NotificationTypes.delivery),
                   daemon=True).start()
    else:
        logger.info(f"Товар для заказа $YELLOW#{deal.id}$RESET выдан: $CYAN{', '.join(products)}$RESET")
        if c.telegram:
            from tg_bot import utils
            from tg_bot.utils import NotificationTypes
            from threading import Thread
            amount = "<b>∞</b>" if goods_left == -1 else f"<code>{goods_left}</code>"
            text = f"""✅ Успешно выдал товар для ордера <code>{deal.id}</code>.\n
🛒 <b><i>Товар:</i></b>
<code>{utils.escape(delivery_text)}</code>\n
📋 <b><i>Осталось товаров: </i></b>{amount}"""
            Thread(target=c.telegram.send_notification, args=(text, None, NotificationTypes.delivery),
                   daemon=True).start()
        from Utils import playerok_automation
        playerok_automation.process_auto_disable_for_lot(c, lot_id, delivery_config)

def chat_initialized_handler(c: Cardinal, event: ChatInitializedEvent):
    chat = event.chat
    chat_name = chat.name if hasattr(chat, 'name') else str(chat.id)
    logger.info(f"Инициализирован чат $YELLOW{chat_name} (ID: {chat.id})$RESET")

def create_deal_keyboard(chat_id: str, username: str, deal_id: str):
    from telebot.types import InlineKeyboardMarkup as K, InlineKeyboardButton as B
    from tg_bot import CBT
    from locales.localizer import Localizer
    
    localizer = Localizer()
    _ = localizer.translate
    
    keyboard = K()
    keyboard.row(
        B(_("msg_reply"), None, f"{CBT.SEND_FP_MESSAGE}:{chat_id}:{username}"),
        B(_("msg_templates"), None, f"{CBT.TMPLT_LIST_ANS_MODE}:0:{chat_id}:{username}:0:0")
    )
    keyboard.row(B(f"🌐 {username}", url=f"https://playerok.com/chats/{chat_id}"))
    keyboard.row(B("📋 Сделка", url=f"https://playerok.com/deals/{deal_id}/"))
    return keyboard

def send_new_deal_notification(c: Cardinal, event: NewDealEvent):
    if not c.telegram:
        return
    
    deal = event.deal
    chat = event.chat
    
    buyer_username = _deal_buyer_username(deal)
    
    if buyer_username in c.blacklist and hasattr(c.MAIN_CFG, 'get') and isinstance(c.MAIN_CFG.get("BlockList"), dict) and c.MAIN_CFG.get("BlockList", {}).get("blockNewOrderNotification") == "1":
        return
    
    item_name = _deal_item_name(deal)
    subcategory_name = ""
    if hasattr(deal, 'item') and deal.item and hasattr(deal.item, 'category') and deal.item.category:
        subcategory_name = deal.item.category.name if hasattr(deal.item.category, 'name') else ""
    
    price_rub = _deal_price_rub(deal)
    
    delivery_config = None
    lot_id = str(deal.item.id) if hasattr(deal, 'item') and deal.item and hasattr(deal.item, 'id') else None
    if lot_id:
        for config in c.AD_CFG:
            if config.get("lot_id") == lot_id:
                delivery_config = config
                break
    
    if not delivery_config:
        delivery_info = _("ntfc_new_order_not_in_cfg")
    else:
        if not c.autodelivery_enabled:
            delivery_info = _("ntfc_new_order_ad_disabled")
        else:
            delivery_info = _("ntfc_new_order_will_be_delivered")
    
    from tg_bot import utils
    description = f"{utils.escape(item_name)}"
    if subcategory_name:
        description += f", {utils.escape(subcategory_name)}"
    
    text = _("ntfc_new_order", description, buyer_username, f"{price_rub:.2f} RUB", deal.id, delivery_info)
    
    keyboard = create_deal_keyboard(str(chat.id), buyer_username, deal.id)
    
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
    keyboard = create_deal_keyboard(str(chat.id), buyer_username, deal.id)
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
    keyboard = create_deal_keyboard(str(chat.id), buyer_username, deal.id)
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
    keyboard = create_deal_keyboard(str(chat.id), buyer_username, deal.id)
    from tg_bot.utils import NotificationTypes
    from threading import Thread
    Thread(target=c.telegram.send_notification, args=(text, keyboard, NotificationTypes.order_confirmed),
           daemon=True).start()

def send_new_review_notification(c: Cardinal, event: NewReviewEvent):
    if c.telegram is None:
        return
    
    deal = event.deal
    chat = event.chat
    
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

    keyboard = create_deal_keyboard(str(chat.id), buyer_username, deal.id)

    from tg_bot.utils import NotificationTypes
    from threading import Thread
    Thread(target=c.telegram.send_notification,
           args=(_("ntfc_new_review").format(stars, deal.id, utils.escape(review_text)),
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
    
    keyboard = create_deal_keyboard(str(chat.id), buyer_username, deal.id)
    
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
    
    keyboard = create_deal_keyboard(str(chat.id), buyer_username, deal.id)
    
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
    keyboard = create_deal_keyboard(str(chat.id), buyer_username, deal.id)
    from tg_bot.utils import NotificationTypes
    from threading import Thread
    Thread(target=c.telegram.send_notification, args=(text, keyboard, NotificationTypes.order_confirmed),
           daemon=True).start()

def auto_restore_handler(c: Cardinal, event: ItemPaidEvent | ItemSentEvent):
    if not c.autorestore_enabled:
        return
    
    deal = event.deal
    if not deal or not deal.item:
        return
    
    from PlayerokAPI import enums
    if hasattr(deal, 'status') and deal.status != enums.ItemDealStatuses.PAID:
        return
    
    item_id = deal.item.id
    item_name = deal.item.name
    
    logger.info(f"🚀 Запуск авто-восстановления для товара {item_name} (ID: {item_id})")
    
    try:
        item_details = c.account.get_item(id=item_id)
        if not item_details:
            logger.error(f"❌ Не удалось получить детали товара {item_name} (ID: {item_id})")
            return
        
        if isinstance(c.MAIN_CFG, dict):
            restore_mode = c.MAIN_CFG.get("Playerok", {}).get("restorePriorityMode", "premium")
        else:
            restore_mode = c.MAIN_CFG.get("Playerok", "restorePriorityMode", fallback="premium")
        
        balance = None
        for attempt in range(3):
            try:
                balance_obj = c.get_balance()
                balance = balance_obj.available if balance_obj and balance_obj.available else 0
                break
            except Exception as e:
                if attempt == 2:
                    balance = None
                    logger.error(f"❌ Ошибка получения баланса: {e}")
                else:
                    time.sleep(1)
        
        item_price = str(item_details.price) if item_details.price else "0"
        price_premium = None
        status_premium_id = None
        status_free_id = "1efbe5bc-99a7-68e5-4534-85dad913b981"
        
        for attempt in range(3):
            try:
                priority_statuses = c.account.get_item_priority_statuses(item_id, item_price)
                if priority_statuses:
                    for status in priority_statuses:
                        status_price = status.price if hasattr(status, 'price') else 0
                        if status_price > 0:
                            if price_premium is None or status_price < price_premium:
                                price_premium = status_price
                                status_premium_id = status.id if hasattr(status, 'id') else None
                break
            except Exception as e:
                if attempt == 2:
                    price_premium = None
                    logger.error(f"❌ Ошибка получения цены премиума: {e}")
                else:
                    time.sleep(1)
        
        if balance is None or price_premium is None:
            skip_balance_check = True
        else:
            skip_balance_check = False
        
        if hasattr(item_details, 'data_fields') and item_details.data_fields:
            has_hidden_fields = any(
                hasattr(field, 'hidden') and field.hidden 
                for field in item_details.data_fields
            )
            if has_hidden_fields:
                return
        
        from PlayerokAPI.types import MyItem
        is_my_item = isinstance(item_details, MyItem)
        
        if is_my_item and item_details.is_editable:
            if hasattr(item_details, 'priority') and item_details.priority:
                priority_name = None
                if hasattr(item_details.priority, 'name'):
                    priority_name = item_details.priority.name
                elif isinstance(item_details.priority, str):
                    priority_name = item_details.priority
                
                if priority_name == 'PREMIUM':
                    if restore_mode == "free":
                        status = status_free_id
                    elif restore_mode == "premium":
                        if not skip_balance_check and price_premium and float(price_premium) <= float(balance):
                            status = status_premium_id if status_premium_id else status_free_id
                        else:
                            status = status_free_id
                    else:
                        status = status_premium_id if status_premium_id else status_free_id
                        if not skip_balance_check and price_premium and float(price_premium) > float(balance):
                            status = status_free_id
                else:
                    status = status_free_id
            else:
                status = status_free_id
            
            for attempt in range(3):
                try:
                    c.account.publish_item(item_id, status)
                    status_text = "премиум" if status == status_premium_id else "бесплатно"
                    
                    if c.telegram:
                        try:
                            from tg_bot.utils import NotificationTypes
                            from threading import Thread
                            text = f"🔄 <b>Авто-восстановление товара</b>\n\n✅ Товар '{item_name}' перевыставлен ({status_text})\n🆔 ID: {item_id}"
                            Thread(target=c.telegram.send_notification, args=(text, None, NotificationTypes.relist),
                                   daemon=True).start()
                        except Exception as notify_ex:
                            logger.error(f"❌ Ошибка отправки уведомления: {notify_ex}")
                    
                    return
                except Exception as e:
                    logger.error(f"❌ Ошибка публикации (попытка {attempt+1}): {e}")
                    if attempt == 2:
                        raise
                    time.sleep(1)
        
        if not item_details.is_editable:
            if restore_mode == "premium" and (balance is None or price_premium is None or status_premium_id is None):
                for attempt in range(3):
                    try:
                        balance_obj = c.get_balance()
                        balance = balance_obj.available if balance_obj and balance_obj.available else 0
                        break
                    except Exception as e:
                        if attempt == 2:
                            balance = None
                            logger.error(f"❌ Ошибка получения баланса: {e}")
                        else:
                            time.sleep(1)
                
                item_price = str(item_details.price) if item_details.price else "0"
                for attempt in range(3):
                    try:
                        priority_statuses = c.account.get_item_priority_statuses(item_id, item_price)
                        if priority_statuses:
                            for status in priority_statuses:
                                status_price = status.price if hasattr(status, 'price') else 0
                                if status_price > 0:
                                    if price_premium is None or status_price < price_premium:
                                        price_premium = status_price
                                        status_premium_id = status.id if hasattr(status, 'id') else None
                        break
                    except Exception as e:
                        if attempt == 2:
                            price_premium = None
                            logger.error(f"❌ Ошибка получения цены премиума: {e}")
                        else:
                            time.sleep(1)
            
            try:
                category_id = item_details.category.id if item_details.category else None
                obtaining_type_id = item_details.obtaining_type.id if item_details.obtaining_type else None
                
                if not obtaining_type_id or not category_id:
                    logger.warning(f"Не удалось получить необходимые данные для товара {item_name}")
                    return
                
                item_data = {
                    "category": {"id": category_id},
                    "name": item_name,
                    "price": item_details.price,
                    "description": item_details.description if hasattr(item_details, 'description') and item_details.description else item_name,
                    "attributes": item_details.attributes if hasattr(item_details, 'attributes') and item_details.attributes else {},
                    "dataFields": [
                        {
                            "fieldId": field.id,
                            "value": field.value
                        }
                        for field in (item_details.data_fields if hasattr(item_details, 'data_fields') and item_details.data_fields else [])
                        if hasattr(field, 'type') and hasattr(field, 'id') and hasattr(field, 'value')
                    ],
                    "obtainingType": {"id": obtaining_type_id},
                    "attachments": []
                }
                
                if hasattr(item_details, 'attachments') and item_details.attachments:
                    for att in item_details.attachments:
                        if hasattr(att, 'url') and att.url:
                            item_data["attachments"].append({"url": att.url})
                
                if not item_data["attachments"]:
                    if c.telegram:
                        from tg_bot.utils import NotificationTypes
                        from threading import Thread
                        text = f"⚠️ <b>Авто-восстановление пропущено</b>\n\nТовар '{item_name}' не имеет изображений\n🆔 ID: {item_id}\n💡 Необходимо создать товар вручную на playerok.com"
                        Thread(target=c.telegram.send_notification, args=(text, None, NotificationTypes.relist),
                               daemon=True).start()
                    return
                
                temp_image_path = None
                try:
                    image_url = item_data["attachments"][0]["url"]
                    
                    response = requests.get(image_url, stream=True, timeout=30)
                    response.raise_for_status()
                    
                    temp_dir = tempfile.gettempdir()
                    temp_image_path = os.path.join(temp_dir, f"autorestore_item_{item_id}_{int(time.time())}.jpg")
                    
                    with open(temp_image_path, "wb") as f:
                        for chunk in response.iter_content(chunk_size=1024):
                            if chunk:
                                f.write(chunk)
                    
                except Exception as download_ex:
                    logger.error(f"❌ Ошибка скачивания изображения для товара {item_name}: {download_ex}")
                    if temp_image_path and os.path.exists(temp_image_path):
                        try:
                            os.remove(temp_image_path)
                        except:
                            pass
                    if c.telegram:
                        from tg_bot.utils import NotificationTypes
                        from threading import Thread
                        error_msg = str(download_ex)[:200]
                        text = f"❌ <b>Ошибка авто-восстановления</b>\n\nНе удалось скачать изображение для товара '{item_name}'\n🆔 ID: {item_id}\n⚠️ Ошибка: {error_msg}"
                        Thread(target=c.telegram.send_notification, args=(text, None, NotificationTypes.relist),
                               daemon=True).start()
                    return
                
                full_query = """mutation createItem($input: CreateItemInput!, $attachments: [Upload!]!) {
  createItem(input: $input, attachments: $attachments) {
    ...RegularItem
    __typename
  }
}

fragment RegularItem on Item {
  ...RegularMyItem
  ...RegularForeignItem
  __typename
}

fragment RegularMyItem on MyItem {
  ...ItemFields
  prevPrice
  priority
  sequence
  priorityPrice
  statusExpirationDate
  comment
  viewsCounter
  statusDescription
  editable
  statusPayment {
    ...StatusPaymentTransaction
    __typename
  }
  moderator {
    id
    username
    __typename
  }
  approvalDate
  deletedAt
  createdAt
  updatedAt
  mayBePublished
  prevFeeMultiplier
  sellerNotifiedAboutFeeChange
  __typename
}

fragment ItemFields on Item {
  id
  slug
  name
  description
  rawPrice
  price
  attributes
  status
  priorityPosition
  sellerType
  feeMultiplier
  user {
    ...ItemUser
    __typename
  }
  buyer {
    ...ItemUser
    __typename
  }
  attachments {
    ...PartialFile
    __typename
  }
  category {
    ...RegularGameCategory
    __typename
  }
  game {
    ...RegularGameProfile
    __typename
  }
  comment
  dataFields {
    ...GameCategoryDataFieldWithValue
    __typename
  }
  obtainingType {
    ...GameCategoryObtainingType
    __typename
  }
  __typename
}

fragment ItemUser on UserFragment {
  ...UserEdgeNode
  __typename
}

fragment UserEdgeNode on UserFragment {
  ...RegularUserFragment
  __typename
}

fragment RegularUserFragment on UserFragment {
  id
  username
  role
  avatarURL
  isOnline
  isBlocked
  rating
  testimonialCounter
  createdAt
  supportChatId
  systemChatId
  __typename
}

fragment PartialFile on File {
  id
  url
  __typename
}

fragment RegularGameCategory on GameCategory {
  id
  slug
  name
  categoryId
  gameId
  obtaining
  options {
    ...RegularGameCategoryOption
    __typename
  }
  props {
    ...GameCategoryProps
    __typename
  }
  noCommentFromBuyer
  instructionForBuyer
  instructionForSeller
  useCustomObtaining
  autoConfirmPeriod
  autoModerationMode
  agreements {
    ...RegularGameCategoryAgreement
    __typename
  }
  feeMultiplier
  __typename
}

fragment RegularGameCategoryOption on GameCategoryOption {
  id
  group
  label
  type
  field
  value
  valueRangeLimit {
    min
    max
    __typename
  }
  __typename
}

fragment GameCategoryProps on GameCategoryPropsObjectType {
  minTestimonials
  minTestimonialsForSeller
  __typename
}

fragment RegularGameCategoryAgreement on GameCategoryAgreement {
  description
  gameCategoryId
  gameCategoryObtainingTypeId
  iconType
  id
  sequence
  __typename
}

fragment RegularGameProfile on GameProfile {
  id
  name
  type
  slug
  logo {
    ...PartialFile
    __typename
  }
  __typename
}

fragment GameCategoryDataFieldWithValue on GameCategoryDataFieldWithValue {
  id
  label
  type
  inputType
  copyable
  hidden
  required
  value
  __typename
}

fragment GameCategoryObtainingType on GameCategoryObtainingType {
  id
  name
  description
  gameCategoryId
  noCommentFromBuyer
  instructionForBuyer
  instructionForSeller
  sequence
  feeMultiplier
  agreements {
    ...MinimalGameCategoryAgreement
    __typename
  }
  props {
    minTestimonialsForSeller
    __typename
  }
  __typename
}

fragment MinimalGameCategoryAgreement on GameCategoryAgreement {
  description
  iconType
  id
  sequence
  __typename
}

fragment StatusPaymentTransaction on Transaction {
  id
  operation
  direction
  providerId
  status
  statusDescription
  statusExpirationDate
  value
  props {
    paymentURL
    __typename
  }
  __typename
}

fragment RegularForeignItem on ForeignItem {
  ...ItemFields
  __typename}"""
                
                input_data = {
                    "gameCategoryId": category_id,
                    "name": item_data["name"],
                    "price": int(item_data["price"]),
                    "description": item_data["description"],
                    "attributes": item_data["attributes"],
                    "dataFields": item_data["dataFields"],
                    "obtainingTypeId": obtaining_type_id
                }
                
                operations = {
                    "operationName": "createItem",
                    "query": full_query,
                    "variables": {
                        "input": input_data,
                        "attachments": [None]
                    }
                }
                
                map_field = {
                    "1": ["variables.attachments.0"]
                }
                
                payload = {
                    "operations": json.dumps(operations, ensure_ascii=False),
                    "map": json.dumps(map_field, ensure_ascii=False)
                }
                
                files = {
                    "1": open(temp_image_path, "rb")
                }
                
                new_item_id = None
                try:
                    headers = {"accept": "*/*"}
                    response = c.account.request("post", f"{c.account.base_url}/graphql", headers, payload, files)
                    
                    result = response.json()
                    if "errors" in result:
                        raise Exception(f"GraphQL ошибка: {result['errors']}")
                    
                    if "data" not in result or "createItem" not in result["data"]:
                        raise Exception(f"Неожиданный ответ от API: {result}")
                    
                    new_item_data = result["data"]["createItem"]
                    new_item_id = new_item_data["id"]
                    
                    if restore_mode == "free":
                        status = status_free_id
                    elif restore_mode == "premium":
                        if balance is not None and price_premium is not None and status_premium_id and float(price_premium) <= float(balance):
                            status = status_premium_id
                        else:
                            status = status_free_id
                    else:
                        status = status_free_id
                    
                    for attempt in range(3):
                        try:
                            c.account.publish_item(new_item_id, status)
                            status_text = "премиум" if status == status_premium_id else "бесплатно"
                            
                            if c.telegram:
                                try:
                                    from tg_bot.utils import NotificationTypes
                                    from threading import Thread
                                    text = f"🔄 <b>Авто-восстановление товара</b>\n\n✅ Создан и опубликован новый товар '{item_name}' ({status_text})\n🆔 Старый ID: {item_id}\n🆔 Новый ID: {new_item_id}"
                                    Thread(target=c.telegram.send_notification, args=(text, None, NotificationTypes.relist),
                                           daemon=True).start()
                                except Exception as notify_ex:
                                    logger.error(f"❌ Ошибка отправки уведомления: {notify_ex}")
                            
                            break
                        except Exception as e:
                            logger.error(f"❌ Ошибка публикации нового товара (попытка {attempt+1}): {e}")
                            if attempt == 2:
                                raise
                            time.sleep(1)
                finally:
                    if "1" in files and not files["1"].closed:
                        files["1"].close()
                    
                    try:
                        os.remove(temp_image_path)
                    except:
                        pass
                        
            except Exception as create_ex:
                logger.error(f"❌ Ошибка при создании нового товара для {item_name}: {create_ex}")
                logger.debug("TRACEBACK", exc_info=True)
                if temp_image_path and os.path.exists(temp_image_path):
                    try:
                        os.remove(temp_image_path)
                    except:
                        pass
                if c.telegram:
                    from tg_bot.utils import NotificationTypes
                    from threading import Thread
                    error_msg = str(create_ex)[:200]
                    text = f"❌ <b>Ошибка авто-восстановления</b>\n\nНе удалось создать новый товар '{item_name}'\n🆔 ID: {item_id}\n⚠️ Ошибка: {error_msg}"
                    Thread(target=c.telegram.send_notification, args=(text, None, NotificationTypes.relist),
                           daemon=True).start()
        
    except Exception as ex:
        logger.error(f"❌ Общая ошибка при авто-перевыставлении товара: {ex}")
        logger.debug("TRACEBACK", exc_info=True)

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
        text += _("poc_init_service_hint")
    for i in c.telegram.init_messages:
        try:
            c.telegram.bot.edit_message_text(text, i[0], i[1])
        except:
            continue


def register_handlers(c: Cardinal):
    logger.info("Регистрация обработчиков...")
    
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
    c.new_deal_handlers.append(auto_delivery_handler)

    from Utils import playerok_automation
    c.new_deal_handlers.append(playerok_automation.try_auto_complete_deal)
    
    c.item_paid_handlers.append(enrich_deal_handler)
    c.item_paid_handlers.append(auto_restore_handler)
    
    c.item_sent_handlers.append(send_item_sent_notification)
    c.deal_confirmed_handlers.append(send_deal_confirmed_notification)
    c.deal_rolled_back_handlers.append(send_deal_rolled_back_notification)
    c.new_review_handlers.append(send_new_review_notification)
    c.deal_has_problem_handlers.append(send_deal_has_problem_notification)
    c.deal_problem_resolved_handlers.append(send_deal_problem_resolved_notification)
    c.deal_status_changed_handlers.append(send_deal_status_changed_notification)
    
    logger.info("Обработчики зарегистрированы!")


BIND_TO_POST_INIT = [send_bot_started_notification_handler]

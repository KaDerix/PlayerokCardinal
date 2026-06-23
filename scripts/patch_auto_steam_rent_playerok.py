"""Patch auto_steam_rent.py for Playerok Cardinal."""
import re
import uuid
from pathlib import Path

P = Path(__file__).resolve().parents[1] / "plugins" / "auto_steam_rent.py"
text = P.read_text(encoding="utf-8")

NEW_UUID = str(uuid.uuid4())

# --- imports ---
text = text.replace(
    "from FunPayAPI.updater.events import NewMessageEvent\n"
    "from FunPayAPI.common.enums import MessageTypes, OrderStatuses\n",
    "from PlayerokAPI.listener.events import NewDealEvent, NewMessageEvent, NewReviewEvent\n",
)

# --- metadata ---
text = re.sub(
    r'NAME = "Auto Rent Steam"\n'
    r'VERSION = "0\.3\.1"\n'
    r'DESCRIPTION = "Автоаренда Steam-аккаунтов на FunPay"\n'
    r'CREDITS = "@embedium"\n'
    r'UUID = "[^"]+"',
    f'NAME = "Auto Steam Rent"\n'
    f'VERSION = "1.0.0-playerok"\n'
    f'DESCRIPTION = "Автоаренда Steam-аккаунтов на Playerok"\n'
    f'CREDITS = "@embedium / @KaDerix"\n'
    f'UUID = "{NEW_UUID}"',
    text,
    count=1,
)

# --- paths & logger ---
text = text.replace(
    'DATA_DIR = Path("data") / "rent_steam_dante"',
    'DATA_DIR = Path("storage") / "plugins" / "auto_steam_rent"',
)
text = text.replace('LOGGER = logging.getLogger("FPC.RentSteamDante")', 'LOGGER = logging.getLogger("POC.auto_steam_rent")')
text = text.replace('log_path = os.path.join(os.path.dirname(__file__), "rent_steam_dante.log")', 'log_path = os.path.join("logs", "auto_steam_rent.log")')

# --- config defaults ---
text = text.replace(
    'DEFAULT_PLUGIN_CONFIG = {\n'
    '    "hours_for_review": 1,\n'
    '    "review_bonus_minutes": 60,\n'
    '    "default_review_bonus_minutes": 60,\n'
    '    "default_rental_hours": 24,\n'
    '    "messages": DEFAULT_MESSAGES,\n'
    '}',
    'DEFAULT_PLUGIN_CONFIG = {\n'
    '    "hours_for_review": 1,\n'
    '    "review_bonus_minutes": 60,\n'
    '    "default_review_bonus_minutes": 60,\n'
    '    "default_rental_hours": 24,\n'
    '    "AUTO_RESTORE_ENABLED": True,\n'
    '    "AUTO_RESTORE_MODE": "premium",\n'
    '    "AUTO_RESTORE_WHEN_FUNDED": True,\n'
    '    "messages": DEFAULT_MESSAGES,\n'
    '}',
)

# --- remove FunPay min display ---
text = re.sub(
    r"\n_FUNPAY_MIN_DISPLAY_AMOUNT = 4\n",
    "\n",
    text,
    count=1,
)
text = re.sub(
    r"def _funpay_display_amount\(free: int\) -> int:.*?\n    return max\(_FUNPAY_MIN_DISPLAY_AMOUNT, free\)\n\n",
    "",
    text,
    flags=re.S,
    count=1,
)

# --- rental hours without quantity ---
text = re.sub(
    r"def _calculate_rental_hours\(\n    lot: Optional\[Dict\[str, Any\]\],\n    order_amount: Any,\n    game_hint: Optional\[str\] = None,\n\) -> float:\n    binding = _resolve_binding_for_lot\(lot, game_hint\)\n    qty = max\(int\(order_amount or 1\), 1\)\n    if not binding:\n        return max\(float\(qty\), 1\.0\)\n    base = float\(binding\.get\(\"rental_hours\"\) or 24\)\n    return max\(base \* qty, 0\.1\)",
    'def _calculate_rental_hours(\n    lot: Optional[Dict[str, Any]],\n    game_hint: Optional[str] = None,\n) -> float:\n    binding = _resolve_binding_for_lot(lot, game_hint)\n    if not binding:\n        cfg = _PLUGIN_CONFIG or _load_plugin_config()\n        return max(float(cfg.get("default_rental_hours", 24)), 0.1)\n    return max(float(binding.get("rental_hours") or 24), 0.1)',
    text,
    count=1,
)

# --- lot lookup item_id + lot_id ---
text = re.sub(
    r'def _get_lot_by_id\(lot_id: str\) -> Optional\[Dict\[str, Any\]\]:\n    """Получает лот по ID"""\n    lots = _load_lots\(\)\n    return next\(\(lot for lot in lots if str\(lot\.get\("lot_id"\)\) == str\(lot_id\)\), None\)',
    'def _get_lot_by_id(lot_id: str) -> Optional[Dict[str, Any]]:\n    """Получает лот по Playerok item UUID (или legacy lot_id)."""\n    lots = _load_lots()\n    for lot in lots:\n        ref = str(lot.get("item_id") or lot.get("lot_id") or "")\n        if ref and ref == str(lot_id):\n            return lot\n    return None',
    text,
    count=1,
)

# --- remove FunPay lot sync block ---
text = re.sub(
    r"def _apply_lot_fields\([\s\S]*?def _sync_lots_for_account\(cardinal, account: Dict\[str, Any\]\) -> None:[\s\S]*?_sync_lots_for_game\(cardinal, game\)\n\n",
    "",
    text,
    count=1,
)

# --- rename send message ---
text = text.replace("_send_funpay_message", "_send_chat_message")
text = text.replace("Failed to send FunPay message", "Failed to send Playerok message")
text = text.replace("Successfully sent FunPay message", "Successfully sent Playerok message")
text = text.replace("Attempting to send FunPay message", "Attempting to send Playerok message")

# --- replace sync calls ---
text = re.sub(
    r"_sync_lot_stock\(CARDINAL, ([^)]+)\)",
    r"restore_rent_lot_after_sale(CARDINAL, str(\1))",
    text,
)
text = re.sub(
    r"_sync_lots_for_game\(CARDINAL, ([^)]+)\)",
    r"_restore_lots_for_game(CARDINAL, \1)",
    text,
)
text = re.sub(
    r"_sync_lots_for_account\(CARDINAL, ([^)]+)\)",
    r"_restore_lots_for_account(CARDINAL, \1)",
    text,
)
text = re.sub(
    r"_sync_lots_for_game\(cardinal, ([^)]+)\)",
    r"_restore_lots_for_game(cardinal, \1)",
    text,
)

# --- init: remove manual handler registration ---
text = re.sub(
    r"        handle_funpay_message\.plugin_uuid = UUID\n"
    r"        if handle_funpay_message not in CARDINAL\.new_message_handlers:\n"
    r"            CARDINAL\.new_message_handlers\.append\(handle_funpay_message\)\n"
    r"            LOGGER\.info\(\"%s FunPay message handler registered successfully\", LOGGER_PREFIX\)\n"
    r"        else:\n"
    r"            LOGGER\.warning\(\"%s FunPay message handler already registered\", LOGGER_PREFIX\)\n\n"
    r"        for lot in _load_lots\(\):\n"
    r"            lid = lot\.get\(\"lot_id\"\)\n"
    r"            if lid:\n"
    r"                try:\n"
    r"                    restore_rent_lot_after_sale\(CARDINAL, str\(lid\)\)\n"
    r"                except Exception as exc:\n"
    r"                    LOGGER\.warning\(\"%s Initial stock sync for lot %s failed: %s\", LOGGER_PREFIX, lid, exc\)\n\n",
    "",
    text,
    count=1,
)

# --- remove _handle_new_order entirely ---
text = re.sub(
    r"\ndef _handle_new_order\(cardinal, order_id: str, chat_id: int, buyer_id: int\) -> None:[\s\S]*?(?=\ndef handle_funpay_message)",
    "\n",
    text,
    count=1,
)

# --- handle_funpay_message -> handle_playerok_message ---
text = text.replace("def handle_funpay_message(cardinal, event: NewMessageEvent)", "def handle_playerok_message(cardinal, event: NewMessageEvent)")

# remove feedback + order paid blocks from message handler
text = re.sub(
    r"def handle_playerok_message\(cardinal, event: NewMessageEvent\) -> None:\n    if getattr\(event\.message, \"type\", None\) == MessageTypes\.NEW_FEEDBACK:\n        process_feedback_from_message\(cardinal, event\)\n        return\n\n",
    "def handle_playerok_message(cardinal, event: NewMessageEvent) -> None:\n",
    text,
    count=1,
)
text = re.sub(
    r"    if author_id == 0 and \"оплатил заказ\" in text\.lower\(\):[\s\S]*?        return\n\n",
    "",
    text,
    count=1,
)

# --- remove old feedback handlers at end ---
text = re.sub(
    r"BIND_TO_PRE_INIT = \[init_plugin\]\n"
    r"BIND_TO_DELETE = \[lambda _: _stop_background_tasks\(\)\]\n"
    r"BIND_TO_API: dict = \{\}\n"
    r"BIND_TO_NEW_FEEDBACK = \[process_feedback\]\n",
    "",
    text,
    count=1,
)

# --- UI text funpay -> playerok ---
text = text.replace("FunPay handler: 🟢 зарегистрирован", "Playerok handler: 🟢 зарегистрирован")
text = text.replace("➕ Добавить лот FunPay", "➕ Привязать лот Playerok")
text = text.replace("🔄 Синхронизация наличия на FunPay", "🔄 Восстановить лот на Playerok")
text = text.replace("🔄 Синхронизация: на FunPay min 4 шт. при 1–3 аккаунтах", "🔄 Автовосстановление лота после продажи (Playerok)")
text = text.replace("📊 FunPay:", "📊 Playerok:")
text = text.replace("ID лота с FunPay", "UUID лота Playerok")
text = text.replace("Срок × количество в заказе FunPay", "Срок аренды из привязки лота")
text = text.replace("в этом чате FunPay", "в этом чате Playerok")
text = text.replace("_normalize_funpay_command_text", "_normalize_command_text")

# --- fix _calculate_rental_hours calls ---
text = re.sub(
    r"hours = _calculate_rental_hours\(lot, quantity, game_hint\)",
    "hours = _calculate_rental_hours(lot, game_hint)",
    text,
)

PLAYEROK_HELPERS = r'''

PENDING_RESTORE_FILE = DATA_DIR / "pending_restore_lots.json"
STATUS_FREE_ID = "1efbe5bc-99a7-68e5-4534-85dad913b981"


def _lot_item_id(lot: Optional[Dict[str, Any]]) -> str:
    if not lot:
        return ""
    return str(lot.get("item_id") or lot.get("lot_id") or "")


def _get_restore_config() -> Dict[str, Any]:
    cfg = _PLUGIN_CONFIG or _load_plugin_config()
    return cfg


def _load_pending_restore() -> List[str]:
    try:
        if PENDING_RESTORE_FILE.exists():
            data = json.loads(PENDING_RESTORE_FILE.read_text(encoding="utf-8"))
            return [str(x) for x in data.get("item_ids", [])]
    except Exception:
        pass
    return []


def _save_pending_restore(item_ids: List[str]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    PENDING_RESTORE_FILE.write_text(
        json.dumps({"item_ids": list(dict.fromkeys(item_ids))}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _add_pending_restore(item_id: str) -> None:
    ids = _load_pending_restore()
    if item_id not in ids:
        ids.append(item_id)
        _save_pending_restore(ids)


def _remove_pending_restore(item_id: str) -> None:
    ids = [i for i in _load_pending_restore() if i != item_id]
    _save_pending_restore(ids)


def _resolve_publish_status(cardinal, item_id: str) -> Optional[str]:
    cfg = _get_restore_config()
    mode = str(cfg.get("AUTO_RESTORE_MODE", "premium")).lower()
    status_free_id = STATUS_FREE_ID
    status_premium_id = None
    price_premium = None
    balance = 0.0
    try:
        balance_obj = cardinal.get_balance()
        balance = float(balance_obj.available or 0) if balance_obj else 0.0
    except Exception as exc:
        LOGGER.warning("%s restore balance error: %s", LOGGER_PREFIX, exc)
    try:
        item_details = cardinal.account.get_item(id=item_id)
        item_price = str(item_details.price) if item_details and item_details.price else "0"
        priority_statuses = cardinal.account.get_item_priority_statuses(item_id, item_price)
        if priority_statuses:
            for status in priority_statuses:
                status_price = status.price if hasattr(status, "price") else 0
                if status_price and status_price > 0:
                    if price_premium is None or status_price < price_premium:
                        price_premium = status_price
                        status_premium_id = status.id if hasattr(status, "id") else None
    except Exception as exc:
        LOGGER.warning("%s restore priority error: %s", LOGGER_PREFIX, exc)
    if mode == "free":
        return status_free_id
    if status_premium_id and price_premium is not None and balance >= float(price_premium):
        return status_premium_id
    if mode == "premium":
        return None
    return status_free_id


def restore_rent_lot_after_sale(cardinal, item_id: str) -> bool:
    if not cardinal or not item_id:
        return False
    cfg = _get_restore_config()
    if not cfg.get("AUTO_RESTORE_ENABLED", True):
        return False
    lot = _get_lot_by_id(item_id)
    if not lot or not _lot_bindings(lot):
        return False
    free, _ = _count_lot_accounts(item_id)
    if free <= 0:
        LOGGER.info("%s restore skip %s: no free accounts", LOGGER_PREFIX, item_id)
        return False
    status = _resolve_publish_status(cardinal, item_id)
    if not status:
        LOGGER.warning("%s restore skip %s: insufficient balance for premium", LOGGER_PREFIX, item_id)
        if cfg.get("AUTO_RESTORE_WHEN_FUNDED", True):
            _add_pending_restore(item_id)
        return False
    for attempt in range(3):
        try:
            cardinal.account.publish_item(item_id, status)
            _remove_pending_restore(item_id)
            LOGGER.info("%s restored item %s (status=%s)", LOGGER_PREFIX, item_id, status)
            return True
        except Exception as exc:
            LOGGER.error("%s restore publish attempt %s: %s", LOGGER_PREFIX, attempt + 1, exc)
            if attempt < 2:
                time.sleep(1)
    return False


def _restore_lots_for_game(cardinal, game: str) -> None:
    if not cardinal or not game:
        return
    for lot_id in _get_lot_ids_for_game(game):
        try:
            restore_rent_lot_after_sale(cardinal, lot_id)
        except Exception as exc:
            LOGGER.warning("%s restore lot %s for game %s: %s", LOGGER_PREFIX, lot_id, game, exc)


def _restore_lots_for_account(cardinal, account: Dict[str, Any]) -> None:
    game = (account.get("game") or "").strip()
    if game:
        _restore_lots_for_game(cardinal, game)


def _process_pending_restore_queue() -> None:
    if not CARDINAL:
        return
    cfg = _get_restore_config()
    if not cfg.get("AUTO_RESTORE_WHEN_FUNDED", True):
        return
    for item_id in list(_load_pending_restore()):
        restore_rent_lot_after_sale(CARDINAL, item_id)


def _send_chat_message(cardinal, chat_id: str | int, message: str, *, watermark: bool = True) -> bool:
    try:
        if hasattr(cardinal, "send_message"):
            if watermark:
                return bool(cardinal.send_message(int(chat_id), message))
            try:
                cardinal.account.send_message(str(chat_id), message, mark_chat_as_read=not getattr(cardinal, "keep_sent_messages_unread", False))
                return True
            except Exception:
                return bool(cardinal.send_message(int(chat_id), message))
        return False
    except Exception as exc:
        LOGGER.error("%s send chat message failed: %s", LOGGER_PREFIX, exc, exc_info=True)
        return False


def _deal_buyer_username(deal) -> str:
    user = getattr(deal, "user", None)
    if user and getattr(user, "username", None):
        return str(user.username)
    item = getattr(deal, "item", None)
    buyer = getattr(item, "buyer", None) if item else None
    if buyer and getattr(buyer, "username", None):
        return str(buyer.username)
    return ""


def _send_no_accounts_message(cardinal, deal, chat) -> None:
    chat_id = getattr(chat, "id", None)
    order_id = getattr(deal, "id", "—")
    buyer = _deal_buyer_username(deal)
    buyer_msg = (
        "❌ Сейчас нет свободных аккаунтов для выдачи.\n\n"
        "Обратитесь к продавцу для возврата средств или повторите попытку позже."
    )
    if chat_id:
        _send_chat_message(cardinal, chat_id, buyer_msg)
    if getattr(cardinal, "telegram", None):
        for admin_id in getattr(cardinal.telegram, "admin_ids", [])[:3]:
            try:
                cardinal.telegram.bot.send_message(
                    admin_id,
                    f"⚠️ Нет аккаунтов для заказа <code>{order_id}</code>\n"
                    f"Покупатель: {buyer or '—'}\n"
                    f"Требуется ручной возврат.",
                    parse_mode="HTML",
                )
            except Exception:
                pass


def handle_new_deal_rent(cardinal, event: NewDealEvent) -> None:
    deal = event.deal
    chat = event.chat
    if not deal or not getattr(deal, "item", None):
        return
    item_id = str(deal.item.id)
    lot = _get_lot_by_id(item_id)
    if not lot:
        return
    if not _lot_bindings(lot):
        LOGGER.warning("%s lot %s has no bindings", LOGGER_PREFIX, item_id)
        return
    order_id = str(getattr(deal, "id", "") or "")
    chat_id = getattr(chat, "id", None)
    buyer_username = _deal_buyer_username(deal)
    buyer_id = None
    user = getattr(deal, "user", None)
    if user and getattr(user, "id", None):
        buyer_id = user.id
    game_hint = _extract_game_from_order(getattr(deal.item, "name", "") or "")
    hours = _calculate_rental_hours(lot, game_hint)
    if order_id:
        existing = _find_rental_by_order_id(order_id)
        if existing and existing.get("status") == "active":
            if chat_id:
                _send_rental_credentials_to_chat(cardinal, existing, chat_id)
            return
    payload = {
        "id": order_id,
        "buyer_id": buyer_id,
        "buyer_username": buyer_username,
        "chat_id": chat_id,
        "note": "",
        "game_hint": game_hint,
    }
    accounts = _get_available_accounts_for_lot(item_id, prefer_game=game_hint)
    if not accounts:
        _send_no_accounts_message(cardinal, deal, chat)
        return
    threading.Thread(
        target=_auto_issue_rental_by_lot,
        args=(item_id, hours, payload),
        daemon=True,
    ).start()


def handle_new_review_bonus(cardinal, event: NewReviewEvent) -> None:
    deal = event.deal
    if not deal:
        return
    review = getattr(deal, "review", None)
    if not review:
        return
    rating = getattr(review, "rating", None)
    if rating != 5:
        LOGGER.debug("%s review bonus skip: rating=%s", LOGGER_PREFIX, rating)
        return
    order_id = str(getattr(deal, "id", "") or "")
    buyer_username = _deal_buyer_username(deal)
    feedback_text = getattr(review, "text", "") or ""
    _handle_review_bonus(cardinal, buyer_username, order_id, feedback_text=feedback_text)


BIND_TO_PRE_INIT = [init_plugin]
BIND_TO_DELETE = [lambda _: _stop_background_tasks()]
BIND_TO_NEW_DEAL = [handle_new_deal_rent]
BIND_TO_NEW_MESSAGE = [handle_playerok_message]
BIND_TO_NEW_REVIEW = [handle_new_review_bonus]
'''

# Insert helpers before LOT_TEMPLATES
marker = "LOT_TEMPLATES = []"
if marker in text and "def restore_rent_lot_after_sale" not in text:
    text = text.replace(marker, PLAYEROK_HELPERS + "\n" + marker)

# scheduler: pending restore check
text = text.replace(
    "                await _check_rental_timers()\n",
    "                await _check_rental_timers()\n                _process_pending_restore_queue()\n",
)

# credentials without watermark
text = text.replace(
    "        success = _send_chat_message(CARDINAL, chat_id, message)",
    "        success = _send_chat_message(CARDINAL, chat_id, message, watermark=False)",
)

# rental entry lot_id -> keep as item_id reference
text = text.replace('"lot_id": lot_id,', '"lot_id": lot_id,\n        "item_id": lot_id,')

P.write_text(text, encoding="utf-8")
print(f"Patched {P} ({len(text.splitlines())} lines), UUID={NEW_UUID}")

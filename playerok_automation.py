"""
Фоновая автоматизация Playerok (поднятие, вывод, деактивация) и обработчики сделок.
"""
from __future__ import annotations

from typing import TYPE_CHECKING
from threading import Thread
from datetime import datetime
import logging
import time

if TYPE_CHECKING:
    from cardinal import Cardinal

from PlayerokAPI.enums import ItemStatuses, ItemDealStatuses, PriorityTypes, TransactionProviderIds
from PlayerokAPI.listener.events import NewDealEvent
import Utils.cardinal_tools as ct

logger = logging.getLogger("POC.automation")


def _cfg_bool(section: dict, key: str) -> bool:
    return section.get(key) == "1"


def _should_run_interval(last_time: str, interval_sec: int) -> bool:
    if not last_time:
        return True
    try:
        last_dt = datetime.fromisoformat(last_time)
    except ValueError:
        return True
    return (datetime.now() - last_dt).total_seconds() >= interval_sec


def bump_item(c: "Cardinal", item) -> bool:
    try:
        name = getattr(item, "name", "") or ""
        name_short = name[:32] + ("..." if len(name) > 32 else "")
        cfg = c.auto_bump_cfg
        if not ct.item_matches_filter(name, cfg):
            return False

        item_id = getattr(item, "id", None)
        if not item_id:
            return False

        raw_price = getattr(item, "raw_price", None) or getattr(item, "price", 0)
        statuses = c.account.get_item_priority_statuses(item_id, str(raw_price))
        prem = next(
            (st for st in statuses if getattr(st, "type", None) == PriorityTypes.PREMIUM or getattr(st, "price", 0) > 0),
            None,
        )
        if not prem:
            logger.warning(f"PREMIUM статус не найден для «{name_short}»")
            return False

        time.sleep(1)
        c.account.increase_item_priority_status(item_id, prem.id)
        logger.info(f"Товар «{name_short}» поднят")
        if c.telegram:
            from tg_bot import utils
            text = f"⬆️ Товар <code>{utils.escape(name)}</code> поднят."
            Thread(target=c.telegram.send_notification, args=(text, None), daemon=True).start()
        return True
    except Exception as e:
        logger.error(f"Ошибка поднятия товара: {e}")
        logger.debug("TRACEBACK", exc_info=True)
        return False


def bump_items(c: "Cardinal") -> None:
    if not c.autoraise_enabled or not c.auto_bump_cfg.get("enabled"):
        return
    try:
        if not hasattr(c.account, "profile") or not c.account.profile:
            c.account.get()
        profile = c.account.profile
        if not profile:
            return
        items = c.account.get_my_items(count=24, statuses=[ItemStatuses.APPROVED])
        item_list = getattr(items, "items", []) or []
        up_items = [it for it in item_list if getattr(it, "priority", None) != PriorityTypes.DEFAULT]
        cnt = 0
        for item in up_items:
            if bump_item(c, item):
                cnt += 1
            time.sleep(1)
        c.auto_bump_cfg["last_time"] = datetime.now().isoformat()
        ct.save_json_config("configs/auto_bump.json", c.auto_bump_cfg)
        logger.info(f"Поднято товаров: {cnt}/{len(up_items)}")
    except Exception as e:
        logger.error(f"Ошибка bump_items: {e}")
        logger.debug("TRACEBACK", exc_info=True)


def bump_items_loop(c: "Cardinal") -> None:
    while True:
        try:
            if c.autoraise_enabled and c.auto_bump_cfg.get("enabled"):
                interval = int(c.auto_bump_cfg.get("interval") or 3600)
                if _should_run_interval(c.auto_bump_cfg.get("last_time", ""), interval):
                    bump_items(c)
        except Exception as e:
            logger.debug(f"bump_items_loop: {e}")
        time.sleep(3)


def try_auto_complete_deal(c: "Cardinal", event: NewDealEvent) -> None:
    if not c.autocomplete_enabled or not c.auto_complete_cfg.get("enabled"):
        return
    deal = event.deal
    item = getattr(deal, "item", None)
    if not item:
        return
    name = getattr(item, "name", "") or ""
    if not name:
        try:
            item = c.account.get_item(item.id)
            name = item.name
        except Exception:
            return
    if not ct.item_matches_filter(name, c.auto_complete_cfg):
        return
    try:
        c.account.update_deal(deal.id, ItemDealStatuses.SENT)
        logger.info(f"Сделка {deal.id} автоматически отмечена как отправленная")
    except Exception as e:
        logger.error(f"auto_complete deal {deal.id}: {e}")


def request_withdrawal(c: "Cardinal") -> bool:
    cfg = c.auto_withdrawal_cfg
    try:
        c.account.get()
        balance = 0
        if hasattr(c.account, "profile") and c.account.profile and c.account.profile.balance:
            balance = getattr(c.account.profile.balance, "withdrawable", 0) or 0
        if balance <= 500:
            logger.info(f"Автовывод: баланс {balance}₽ слишком мал (мин. 500₽)")
            return False

        cred_type = (cfg.get("credentials_type") or "").lower()
        sbp_bank_member_id = None
        if cred_type == "card":
            provider = TransactionProviderIds.BANK_CARD_RU
            account = cfg.get("card_id", "")
        elif cred_type == "sbp":
            provider = TransactionProviderIds.SBP
            account = cfg.get("sbp_phone_number", "")
            sbp_bank_member_id = cfg.get("sbp_bank_id") or None
        elif cred_type == "usdt":
            provider = TransactionProviderIds.USDT
            account = cfg.get("usdt_address", "")
        else:
            logger.warning("Автовывод: не задан credentials_type в configs/auto_withdrawal.json")
            return False

        if not account:
            logger.warning("Автовывод: не указаны реквизиты")
            return False

        trans = c.account.request_withdrawal(
            provider=provider,
            account=account,
            value=balance,
            sbp_bank_member_id=sbp_bank_member_id,
        )
        cfg["last_time"] = datetime.now().isoformat()
        ct.save_json_config("configs/auto_withdrawal.json", cfg)
        c.auto_withdrawal_cfg = cfg
        logger.info(f"Создана транзакция на вывод {balance}₽")
        if c.telegram:
            text = f"💳 Транзакция на вывод <b>{balance}₽</b> создана."
            if trans and hasattr(trans, "id"):
                text += f"\nID: <code>{trans.id}</code>"
            Thread(target=c.telegram.send_notification, args=(text, None), daemon=True).start()
        return True
    except Exception as e:
        logger.error(f"Ошибка автовывода: {e}")
        if c.telegram:
            Thread(
                target=c.telegram.send_notification,
                args=(f"❌ Ошибка автовывода: {e}", None),
                daemon=True,
            ).start()
        return False


def withdrawal_loop(c: "Cardinal") -> None:
    while True:
        try:
            if c.autowithdrawal_enabled and c.auto_withdrawal_cfg.get("enabled"):
                interval = int(c.auto_withdrawal_cfg.get("interval") or 86400)
                if _should_run_interval(c.auto_withdrawal_cfg.get("last_time", ""), interval):
                    request_withdrawal(c)
        except Exception as e:
            logger.debug(f"withdrawal_loop: {e}")
        time.sleep(3)


def check_products_amount(delivery_config: dict) -> bool:
    goods_file = delivery_config.get("goods_file")
    if not goods_file:
        return False
    return ct.count_products(goods_file) > 0


def process_auto_disable_for_lot(c: "Cardinal", lot_id: str, delivery_config: dict) -> None:
    if not c.autodisable_enabled:
        return
    if delivery_config.get("disableAutoDisable") in ("1", True):
        return
    if check_products_amount(delivery_config):
        return
    try:
        c.account.remove_item(lot_id)
        lot_name = delivery_config.get("lot_id", lot_id)
        logger.info(f"Лот {lot_id} деактивирован (нет товаров)")
        if c.telegram:
            text = f"🔴 <b>Деактивирован лот</b> (нет товаров)\n<code>{lot_name}</code>"
            Thread(target=c.telegram.send_notification, args=(text, None), daemon=True).start()
    except Exception as e:
        logger.error(f"auto_disable {lot_id}: {e}")


def auto_disable_loop(c: "Cardinal") -> None:
    while True:
        try:
            if c.autodisable_enabled and c.AD_CFG:
                for cfg in c.AD_CFG:
                    lot_id = cfg.get("lot_id")
                    if lot_id:
                        process_auto_disable_for_lot(c, str(lot_id), cfg)
                    time.sleep(0.3)
        except Exception as e:
            logger.debug(f"auto_disable_loop: {e}")
        time.sleep(60)


from __future__ import annotations

import logging
import os
import tempfile
import time
from typing import TYPE_CHECKING, Any

import requests

if TYPE_CHECKING:
    from cardinal import Cardinal

logger = logging.getLogger("POC.item_restore")

STATUS_FREE_ID = "1efbe5bc-99a7-68e5-4534-85dad913b981"
_recreated_ids: set[str] = set()


def _is_rate_limit(exc: BaseException) -> bool:
    msg = str(exc).lower()
    return any(x in msg for x in ("слишком много", "too many", "rate limit", "повторить"))


def _is_not_found(exc: BaseException) -> bool:
    msg = str(exc).lower()
    return any(x in msg for x in ("не удалось найти", "not found", "айди"))


def _short(name: str, n: int = 40) -> str:
    name = name or ""
    return name if len(name) <= n else name[: n - 1] + "…"


def _pick_status(c: "Cardinal", item_id: str, price, prefer_premium: bool = False):
    from PlayerokAPI.enums import PriorityTypes

    if isinstance(c.MAIN_CFG, dict):
        mode = c.MAIN_CFG.get("Playerok", {}).get("restorePriorityMode", "free")
    else:
        mode = c.MAIN_CFG.get("Playerok", "restorePriorityMode", fallback="free")

    free_id, prem_id, prem_price = STATUS_FREE_ID, None, None
    try:
        statuses = c.account.get_item_priority_statuses(item_id, str(price or 0)) or []
        for st in statuses:
            sp = getattr(st, "price", 0) or 0
            st_type = getattr(st, "type", None)
            if sp == 0 or st_type == PriorityTypes.DEFAULT:
                free_id = getattr(st, "id", None) or free_id
            if sp > 0 or st_type == PriorityTypes.PREMIUM:
                if prem_price is None or sp < prem_price:
                    prem_price = sp
                    prem_id = getattr(st, "id", None)
    except Exception as e:
        logger.debug("priority statuses %s: %s", item_id, e)

    balance = 0.0
    try:
        bal = c.get_balance()
        balance = float(getattr(bal, "available", 0) or 0) if bal else 0.0
    except Exception:
        pass

    want_prem = prefer_premium or mode == "premium"
    if want_prem and prem_id and prem_price is not None and balance >= float(prem_price):
        return prem_id, True
    return free_id, False


def find_sold_item_by_name(c: "Cardinal", name: str, priority=None, retries: int = 3, delay: float = 4.0):
    from PlayerokAPI.enums import ItemStatuses

    name = (name or "").strip()
    if not name:
        return None

    last_err = None
    for attempt in range(1, retries + 1):
        try:
            page = c.account.get_my_items(statuses=[ItemStatuses.SOLD], count=24)
            items = list(getattr(page, "items", None) or [])
            info = getattr(page, "page_info", None)
            if info and getattr(info, "has_next_page", False) and getattr(info, "end_cursor", None):
                page2 = c.account.get_my_items(
                    statuses=[ItemStatuses.SOLD], count=24, after_cursor=info.end_cursor
                )
                items.extend(getattr(page2, "items", None) or [])

            same_name = [it for it in items if (getattr(it, "name", None) or "").strip() == name]
            if not same_name:
                raise LookupError("not in SOLD yet")

            if priority is not None:
                matched = next(
                    (it for it in same_name if getattr(it, "priority", None) == priority),
                    None,
                )
                if matched:
                    return matched
            return same_name[0]
        except Exception as e:
            last_err = e
            sleep_for = delay * 2 if _is_rate_limit(e) else delay
            if attempt < retries:
                time.sleep(sleep_for)

    if last_err:
        logger.debug("find_sold_item_by_name(%s): %s", _short(name), last_err)
    return None


def _get_full_item(c: "Cardinal", item_id: str):
    try:
        return c.account.get_item(id=str(item_id))
    except Exception as e:
        logger.debug("get_item %s: %s", item_id, e)
        return None


def _download_attachments(item) -> list[str]:
    paths: list[str] = []
    for att in getattr(item, "attachments", None) or []:
        url = getattr(att, "url", None)
        if not url:
            continue
        try:
            r = requests.get(url, timeout=30)
            r.raise_for_status()
            ext = ".jpg"
            ct = (r.headers.get("content-type") or "").lower()
            if "png" in ct:
                ext = ".png"
            elif "webp" in ct:
                ext = ".webp"
            fd, path = tempfile.mkstemp(prefix="poc_restore_", suffix=ext)
            os.close(fd)
            with open(path, "wb") as f:
                f.write(r.content)
            paths.append(path)
            time.sleep(0.5)
        except Exception as e:
            logger.debug("download attachment: %s", e)
    return paths


def _create_item_copy(c: "Cardinal", item) -> Any:
    from PlayerokAPI.enums import GameCategoryDataFieldTypes

    cat = getattr(item, "category", None)
    obt = getattr(item, "obtaining_type", None)
    if not cat or not getattr(cat, "id", None) or not obt or not getattr(obt, "id", None):
        raise RuntimeError("нет category/obtaining_type для пересоздания")

    attrs = getattr(item, "attributes", None) or {}
    if not isinstance(attrs, dict):
        attrs = {}

    data_fields = []
    for f in getattr(item, "data_fields", None) or []:
        ftype = getattr(f, "type", None)
        if ftype == GameCategoryDataFieldTypes.ITEM_DATA or (
            ftype and getattr(ftype, "name", "") == "ITEM_DATA"
        ):
            data_fields.append(f)

    attachments = _download_attachments(item)
    try:
        price = getattr(item, "raw_price", None) or getattr(item, "price", None) or 0
        time.sleep(1)
        return c.account.create_item(
            game_category_id=str(cat.id),
            obtaining_type_id=str(obt.id),
            name=getattr(item, "name", "") or "item",
            price=int(price),
            description=getattr(item, "description", None) or "",
            options=attrs,
            data_fields=data_fields,
            attachments=attachments,
        )
    finally:
        for p in attachments:
            try:
                os.remove(p)
            except Exception:
                pass


def _remove_quietly(c: "Cardinal", item_id: str, what: str, name_frmtd: str) -> bool:
    for _ in range(3):
        try:
            time.sleep(1)
            c.account.remove_item(str(item_id))
            return True
        except Exception as e:
            last = e
    logger.warning("«%s» — не удалось удалить %s: %s", name_frmtd, what, last)
    return False


def _notify(c: "Cardinal", text: str) -> None:
    if not c.telegram:
        return
    try:
        from tg_bot.utils import NotificationTypes
        from threading import Thread
        Thread(
            target=c.telegram.send_notification,
            args=(text, None, NotificationTypes.relist),
            daemon=True,
        ).start()
    except Exception:
        pass


def _publish(c: "Cardinal", item_id: str, price, is_premium: bool = False):
    status_id, used_prem = _pick_status(c, item_id, price, prefer_premium=is_premium)
    time.sleep(1)
    try:
        new_item = c.account.publish_item(item_id, status_id)
        return new_item, used_prem
    except Exception as e:
        if not used_prem:
            status_id2, used2 = _pick_status(c, item_id, price, prefer_premium=True)
            if used2 and status_id2 != status_id:
                logger.warning(
                    "«%s» — free publish не вышел, пробую premium: %s",
                    item_id, e,
                )
                time.sleep(1)
                new_item = c.account.publish_item(item_id, status_id2)
                return new_item, True
        raise e


def restore_after_sale(
    c: "Cardinal",
    *,
    item_id: str,
    item_name: str,
    deal_item=None,
) -> bool:
    from Utils import lots_cache
    from PlayerokAPI.enums import PriorityTypes
    from PlayerokAPI.types import MyItem

    item_id = str(item_id or "")
    item_name = (item_name or "").strip() or item_id
    name_frmtd = _short(item_name)
    priority = getattr(deal_item, "priority", None) if deal_item is not None else None

    sold = find_sold_item_by_name(c, item_name, priority=priority, retries=3, delay=4.0)
    if sold is None and item_name:
        sold = find_sold_item_by_name(c, item_name, priority=None, retries=2, delay=3.0)

    target_id = str(getattr(sold, "id", None) or item_id)
    full = _get_full_item(c, target_id)
    if full is None and sold is not None and getattr(sold, "id", None) and str(sold.id) != target_id:
        full = _get_full_item(c, str(sold.id))
    if full is None and deal_item is not None and isinstance(deal_item, MyItem):
        full = deal_item
    if full is None:
        full = sold

    if full is None:
        logger.error("❌ Restore «%s»: не нашли карточку в SOLD", name_frmtd)
        return False

    try:
        from handlers import _restore_skip_reason
        skip = _restore_skip_reason(c, full)
        if skip:
            logger.info("Авто-восстановление пропуск «%s»: %s", name_frmtd, skip)
            return False
    except Exception:
        pass

    priority = getattr(full, "priority", None) or priority
    is_premium = priority == PriorityTypes.PREMIUM or (
        isinstance(priority, str) and str(priority).upper() == "PREMIUM"
    )
    price = getattr(full, "raw_price", None) or getattr(full, "price", None) or 0
    may_pub = getattr(full, "may_be_published", None)
    old_id = str(getattr(full, "id", target_id))

    need_recreate = may_pub is False

    def _do_recreate() -> bool:
        if old_id in _recreated_ids:
            logger.info("Restore «%s»: уже пересоздавали в этой сессии", name_frmtd)
            return True
        src = full
        if not isinstance(src, MyItem) or not getattr(src, "category", None) or not getattr(src, "obtaining_type", None):
            src2 = _get_full_item(c, old_id)
            if src2 is not None:
                src = src2
        logger.info("Restore «%s»: mayBePublished=%s → пересоздание", name_frmtd, may_pub)
        draft = _create_item_copy(c, src)
        draft_id = str(draft.id)
        try:
            new_item, used_prem = _publish(c, draft_id, price, is_premium=is_premium)
        except Exception:
            _remove_quietly(c, draft_id, "черновик после неудачной публикации", name_frmtd)
            raise
        _recreated_ids.add(old_id)
        lots_cache.upsert(new_item)
        lots_cache.save()
        status_text = "премиум" if used_prem else "бесплатно"
        new_id = getattr(new_item, "id", draft_id)
        logger.info("✅ Товар «%s» пересоздан (%s) · новый ID %s", name_frmtd, status_text, new_id)
        try:
            from handlers import _sync_ad_lot_id
            _sync_ad_lot_id(c, item_name, str(new_id))
        except Exception:
            pass
        _notify(
            c,
            f"🔄 <b>Авто-восстановление</b>\n\n"
            f"✅ «{item_name}» пересоздан и выставлен ({status_text})\n"
            f"🆔 <code>{new_id}</code>",
        )
        _remove_quietly(c, old_id, "старый товар после пересоздания", name_frmtd)
        return True

    if need_recreate:
        try:
            return _do_recreate()
        except Exception as e:
            logger.error("❌ Пересоздание «%s» не удалось: %s", name_frmtd, e)
            return False

    logger.info("Restore «%s»: publish %s", name_frmtd, old_id)
    last_err = None
    for attempt in range(1, 4):
        try:
            new_item, used_prem = _publish(c, old_id, price, is_premium=is_premium)
            lots_cache.upsert_dict({
                "id": old_id,
                "name": item_name,
                "price": price,
                "status": "APPROVED",
            })
            lots_cache.save()
            status_text = "премиум" if used_prem else "бесплатно"
            logger.info("✅ Товар «%s» восстановлен (%s) · %s", name_frmtd, status_text, old_id)
            _notify(
                c,
                f"🔄 <b>Авто-восстановление товара</b>\n\n"
                f"✅ «{item_name}» снова в продаже ({status_text})\n"
                f"🆔 <code>{old_id}</code>",
            )
            return True
        except Exception as e:
            last_err = e
            logger.warning("publish «%s» попытка %s/3: %s", name_frmtd, attempt, e)
            if _is_not_found(e) or attempt >= 2:
                logger.info("Restore «%s»: publish недоступен → пересоздание", name_frmtd)
                try:
                    return _do_recreate()
                except Exception as e2:
                    logger.error("❌ Fallback recreate «%s»: %s", name_frmtd, e2)
                    return False
            if _is_rate_limit(e):
                time.sleep(10)
            else:
                time.sleep(3)

    logger.error("❌ Не удалось восстановить «%s»: %s", name_frmtd, last_err)
    return False

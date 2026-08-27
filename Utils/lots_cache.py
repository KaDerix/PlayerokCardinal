from __future__ import annotations

import json
import logging
import os
import threading
import time
from typing import Any

logger = logging.getLogger("POC.lots_cache")

CACHE_PATH = os.path.join("storage", "cache", "listed_lots.json")
POLL_INTERVAL_SEC = 10
RATE_LIMIT_SLEEP_SEC = 45

_CACHE: dict[str, dict[str, Any]] = {}
_LOADED = False
_WATCH_STARTED = False
_WATCH_LOCK = threading.Lock()
_REFRESH_LOCK = threading.Lock()
_RATE_LIMITED_UNTIL = 0.0


def _norm_item(item) -> dict[str, Any] | None:
    if not item or not getattr(item, "id", None):
        return None
    cat = getattr(item, "category", None)
    st = getattr(item, "status", None)
    return {
        "id": str(item.id),
        "name": getattr(item, "name", None) or "",
        "price": getattr(item, "price", None) or 0,
        "status": st.name if st is not None and hasattr(st, "name") else str(st or ""),
        "category_id": str(getattr(cat, "id", "") or "") if cat else "",
        "category_slug": (getattr(cat, "slug", None) or "") if cat else "",
        "category_name": (getattr(cat, "name", None) or "") if cat else "",
        "updated_at": time.time(),
    }


def get(item_id: str) -> dict[str, Any] | None:
    _ensure_loaded()
    return _CACHE.get(str(item_id))


def upsert(item) -> None:
    row = _norm_item(item)
    if not row:
        return
    _CACHE[row["id"]] = row


def upsert_dict(data: dict[str, Any]) -> None:
    item_id = str(data.get("id") or "").strip()
    if not item_id:
        return
    cur = _CACHE.get(item_id, {})
    cur.update({k: v for k, v in data.items() if v is not None})
    cur["id"] = item_id
    cur["updated_at"] = time.time()
    _CACHE[item_id] = cur


def all_items() -> dict[str, dict[str, Any]]:
    _ensure_loaded()
    return dict(_CACHE)


def save() -> None:
    try:
        os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)
        with open(CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump({"saved_at": time.time(), "items": _CACHE}, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.debug("Не удалось сохранить кэш лотов: %s", e)


def _ensure_loaded() -> None:
    global _LOADED
    if _LOADED:
        return
    _LOADED = True
    try:
        if not os.path.exists(CACHE_PATH):
            return
        with open(CACHE_PATH, "r", encoding="utf-8") as f:
            raw = json.load(f)
        items = raw.get("items") if isinstance(raw, dict) else None
        if isinstance(items, dict):
            for k, v in items.items():
                if isinstance(v, dict):
                    _CACHE[str(k)] = v
    except Exception as e:
        logger.debug("Не удалось загрузить кэш лотов: %s", e)


def _is_rate_limit_error(exc: BaseException) -> bool:
    msg = str(exc).lower()
    return any(x in msg for x in (
        "слишком много",
        "too many",
        "rate limit",
        "попробуйте повторить",
        "try again later",
    ))


def refresh_from_account(account) -> int:
    global _RATE_LIMITED_UNTIL
    from PlayerokAPI.enums import ItemStatuses

    _ensure_loaded()
    if time.time() < _RATE_LIMITED_UNTIL:
        return len(_CACHE)

    if not _REFRESH_LOCK.acquire(blocking=False):
        return len(_CACHE)

    try:
        statuses = [
            ItemStatuses.APPROVED,
            ItemStatuses.PENDING_APPROVAL,
            ItemStatuses.PENDING_MODERATION,
            ItemStatuses.DRAFT,
        ]
        cursor = None
        seen_ids: set[str] = set()
        for _page in range(20):
            try:
                page = account.get_my_items(statuses=statuses, count=24, after_cursor=cursor)
            except Exception as e:
                if _is_rate_limit_error(e):
                    _RATE_LIMITED_UNTIL = time.time() + RATE_LIMIT_SLEEP_SEC
                    logger.debug("Лимит API при опросе лотов — пауза %sс", RATE_LIMIT_SLEEP_SEC)
                else:
                    logger.debug("Опрос лотов: %s", e)
                break

            for it in getattr(page, "items", None) or []:
                upsert(it)
                seen_ids.add(str(it.id))

            info = getattr(page, "page_info", None)
            if not info or not getattr(info, "has_next_page", False):
                break
            cursor = getattr(info, "end_cursor", None)
            if not cursor:
                break
            time.sleep(0.4)

        for old_id in list(_CACHE.keys()):
            if old_id not in seen_ids:
                st = (_CACHE[old_id].get("status") or "").upper()
                if st in ("SOLD", "EXPIRED", ""):
                    _CACHE.pop(old_id, None)

        save()
        return len(_CACHE)
    finally:
        _REFRESH_LOCK.release()


def start_watch_loop(cardinal) -> bool:
    global _WATCH_STARTED
    with _WATCH_LOCK:
        if _WATCH_STARTED:
            return False
        _WATCH_STARTED = True

    def _loop():
        logger.info("✦ Запущена проверка лотов (каждые %sс)", POLL_INTERVAL_SEC)
        try:
            pending_path = os.path.join("storage", "cache", "pending_restore_items.json")
            os.makedirs(os.path.dirname(pending_path), exist_ok=True)
            with open(pending_path, "w", encoding="utf-8") as f:
                json.dump({"items": []}, f)
        except Exception:
            pass
        time.sleep(5)
        while getattr(cardinal, "running", True):
            try:
                if getattr(cardinal, "running", True):
                    refresh_from_account(cardinal.account)
            except Exception as e:
                logger.debug("Ошибка цикла лотов: %s", e)
            for _ in range(POLL_INTERVAL_SEC):
                if not getattr(cardinal, "running", True):
                    return
                time.sleep(1)

    threading.Thread(target=_loop, name="lots-watch", daemon=True).start()
    return True


class SnapshotItem:
    def __init__(self, data: dict[str, Any]):
        self.id = data.get("id")
        self.name = data.get("name")
        self.price = data.get("price")
        self.category = None
        if data.get("category_id") or data.get("category_slug") or data.get("category_name"):
            self.category = type("Cat", (), {
                "id": data.get("category_id") or None,
                "slug": data.get("category_slug") or None,
                "name": data.get("category_name") or None,
            })()


def as_item(item_id: str):
    row = get(item_id)
    if not row:
        return None
    return SnapshotItem(row)

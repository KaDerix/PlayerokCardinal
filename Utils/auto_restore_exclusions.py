"""
Исключения авто-восстановления: конкретные лоты и категории.

configs/auto_restore_exclusions.json:
{
  "lots": ["<item_uuid>", ...],
  "categories": ["stars", "<category_uuid>", "Звёзды", ...]
}
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any

logger = logging.getLogger("POC.auto_restore_exclusions")

CONFIG_PATH = os.path.join("configs", "auto_restore_exclusions.json")


def _norm(value: Any) -> str:
    return str(value or "").strip().lower().replace("ё", "е")


def default_exclusions() -> dict[str, list[str]]:
    return {"lots": [], "categories": []}


def load_exclusions(path: str = CONFIG_PATH) -> dict[str, list[str]]:
    data = default_exclusions()
    try:
        if not os.path.exists(path):
            return data
        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        if not isinstance(raw, dict):
            return data
        lots = raw.get("lots") or []
        cats = raw.get("categories") or []
        data["lots"] = [str(x).strip() for x in lots if str(x).strip()]
        data["categories"] = [str(x).strip() for x in cats if str(x).strip()]
    except Exception as e:
        logger.warning("Не удалось прочитать %s: %s", path, e)
    return data


def save_exclusions(data: dict[str, list[str]], path: str = CONFIG_PATH) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    clean = {
        "lots": sorted({str(x).strip() for x in (data.get("lots") or []) if str(x).strip()}),
        "categories": sorted({str(x).strip() for x in (data.get("categories") or []) if str(x).strip()},
                             key=lambda s: s.lower()),
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(clean, f, ensure_ascii=False, indent=2)


def add_lot(item_id: str, path: str = CONFIG_PATH) -> bool:
    item_id = str(item_id or "").strip()
    if not item_id:
        return False
    data = load_exclusions(path)
    if item_id in data["lots"]:
        return False
    data["lots"].append(item_id)
    save_exclusions(data, path)
    return True


def remove_lot(item_id: str, path: str = CONFIG_PATH) -> bool:
    item_id = str(item_id or "").strip()
    data = load_exclusions(path)
    if item_id not in data["lots"]:
        return False
    data["lots"] = [x for x in data["lots"] if x != item_id]
    save_exclusions(data, path)
    return True


def add_category(value: str, path: str = CONFIG_PATH) -> bool:
    value = str(value or "").strip()
    if not value:
        return False
    data = load_exclusions(path)
    # без дублей без учёта регистра
    existing = {_norm(x) for x in data["categories"]}
    if _norm(value) in existing:
        return False
    data["categories"].append(value)
    save_exclusions(data, path)
    return True


def remove_category(value: str, path: str = CONFIG_PATH) -> bool:
    value = str(value or "").strip()
    data = load_exclusions(path)
    needle = _norm(value)
    new_cats = [x for x in data["categories"] if _norm(x) != needle]
    if len(new_cats) == len(data["categories"]):
        return False
    data["categories"] = new_cats
    save_exclusions(data, path)
    return True


def is_lot_excluded(item_id: str, exclusions: dict[str, list[str]] | None = None) -> bool:
    item_id = str(item_id or "").strip()
    if not item_id:
        return False
    data = exclusions if exclusions is not None else load_exclusions()
    return item_id in set(data.get("lots") or [])


def is_category_excluded(item, exclusions: dict[str, list[str]] | None = None) -> str | None:
    """
    Если категория товара в исключениях — вернуть совпавшее правило, иначе None.
    Сравнивает id / slug / name категории с записями в exclusions.categories.
    """
    cat = getattr(item, "category", None) if item is not None else None
    if not cat:
        return None
    data = exclusions if exclusions is not None else load_exclusions()
    rules = [_norm(x) for x in (data.get("categories") or []) if _norm(x)]
    if not rules:
        return None

    candidates = []
    for attr in ("id", "slug", "name"):
        val = getattr(cat, attr, None)
        if val is not None and str(val).strip():
            candidates.append((attr, str(val).strip(), _norm(val)))

    for attr, original, normalized in candidates:
        if normalized in rules:
            return original if attr != "name" else f"{attr}:{original}"
    return None


def exclusion_reason_for_item(item, exclusions: dict[str, list[str]] | None = None) -> str | None:
    """Человекочитаемая причина пропуска restore из файла исключений."""
    data = exclusions if exclusions is not None else load_exclusions()
    item_id = str(getattr(item, "id", "") or "")
    if item_id and is_lot_excluded(item_id, data):
        return f"лот в исключениях ({item_id})"
    hit = is_category_excluded(item, data)
    if hit:
        return f"категория в исключениях ({hit})"
    return None

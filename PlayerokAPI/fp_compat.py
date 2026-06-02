"""
FunPay API compatibility layer for Playerok Cardinal plugins.
"""
from __future__ import annotations

import json
import os
from logging import getLogger
from typing import Any

from PlayerokAPI.enums import ItemStatuses, PriorityTypes
from Utils.playerok_tg_profile import SubCategoryStub

logger = getLogger("POC.fp_compat")

FP_SUBCATEGORY_ID = 0
DEACTIVATE_PRICE = 99_999_999
_STATE_FILE = "storage/fp_compat_state.json"


class SubCategoryTypes:
    COMMON = "COMMON"


class LotFields:
    """FunPay-like lot fields built from a Playerok item."""

    def __init__(
        self,
        lot_id: str | int,
        *,
        active: bool = True,
        price: float = 0.0,
        title_ru: str = "",
        title_en: str = "",
        description_ru: str = "",
        description_en: str = "",
        fields_dict: dict[str, str] | None = None,
        item: Any = None,
    ):
        self.lot_id = lot_id
        self.active = active
        self.price = price
        self.title_ru = title_ru
        self.title_en = title_en
        self.description_ru = description_ru
        self.description_en = description_en
        self._fields_dict = fields_dict or {}
        self._item = item

    @property
    def fields(self) -> dict[str, str]:
        return self._fields_dict

    def renew_fields(self) -> None:
        pass


def _load_state() -> dict:
    if not os.path.exists(_STATE_FILE):
        return {"deact_backup": {}, "soft_deactivated": []}
    try:
        with open(_STATE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return {"deact_backup": {}, "soft_deactivated": []}
        data.setdefault("deact_backup", {})
        data.setdefault("soft_deactivated", [])
        return data
    except Exception as ex:
        logger.debug("fp_compat state load: %s", ex)
        return {"deact_backup": {}, "soft_deactivated": []}


def _save_state(account) -> None:
    try:
        os.makedirs(os.path.dirname(_STATE_FILE), exist_ok=True)
        with open(_STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "deact_backup": account._fp_deact_backup,
                    "soft_deactivated": sorted(account._fp_soft_deactivated),
                },
                f,
                indent=2,
                ensure_ascii=False,
            )
    except Exception as ex:
        logger.debug("fp_compat state save: %s", ex)


def _build_fields_dict(item) -> dict[str, str]:
    out: dict[str, str] = {}
    obtaining = getattr(item, "obtaining_type", None)
    if obtaining is not None:
        name = getattr(obtaining, "name", None) or ""
        if name:
            out["Способ получения"] = str(name)
    for df in getattr(item, "data_fields", None) or []:
        label = getattr(df, "label", None) or getattr(df, "id", None) or ""
        value = getattr(df, "value", None)
        if label and value is not None and str(value).strip():
            out[str(label)] = str(value)
    name = getattr(item, "name", None) or ""
    desc = getattr(item, "description", None) or ""
    if name:
        out["summary"] = str(name)
    if desc:
        out["description"] = str(desc)
    return out


def _item_price_rub(item) -> float:
    try:
        return float(getattr(item, "price", 0) or 0)
    except (TypeError, ValueError):
        return 0.0


def _item_is_active(account, item) -> bool:
    iid = str(getattr(item, "id", ""))
    if iid in account._fp_soft_deactivated:
        return False
    status = getattr(item, "status", None)
    return status == ItemStatuses.APPROVED


def _item_to_lot_fields(account, item) -> LotFields:
    name = getattr(item, "name", None) or ""
    desc = getattr(item, "description", None) or ""
    return LotFields(
        lot_id=getattr(item, "id", ""),
        active=_item_is_active(account, item),
        price=_item_price_rub(item),
        title_ru=name,
        title_en=name,
        description_ru=desc,
        description_en=desc,
        fields_dict=_build_fields_dict(item),
        item=item,
    )


def _publish_default(account, item_id: str, item) -> None:
    raw_price = getattr(item, "raw_price", None) or getattr(item, "price", 0) or 0
    statuses = account.get_item_priority_statuses(item_id, str(raw_price))
    if not statuses:
        return
    pr_status = next(
        (
            st
            for st in statuses
            if getattr(st, "type", None) == PriorityTypes.DEFAULT or getattr(st, "price", 0) == 0
        ),
        statuses[0],
    )
    account.publish_item(item_id, pr_status.id)


def apply_fp_compat(account) -> None:
    """Attach FunPay-compatible methods to a Playerok Account instance."""
    if getattr(account, "_fp_compat_applied", False):
        return

    state = _load_state()
    account._fp_deact_backup = {str(k): v for k, v in (state.get("deact_backup") or {}).items()}
    account._fp_soft_deactivated = {str(x) for x in (state.get("soft_deactivated") or [])}
    account._fp_lot_fields_cache: dict[str, LotFields] = {}

    def get_subcategory(_sub_type, sid):  # noqa: ARG001
        return SubCategoryStub(id=FP_SUBCATEGORY_ID, name=str(sid or ""))

    def get_lot_fields(lot_id):
        iid = str(lot_id)
        try:
            item = account.get_item(id=iid)
        except Exception as ex:
            logger.debug("get_lot_fields(%s): %s", lot_id, ex)
            return account._fp_lot_fields_cache.get(iid)
        if item is None:
            return None
        fields = _item_to_lot_fields(account, item)
        account._fp_lot_fields_cache[iid] = fields
        return fields

    def save_lot(fields: LotFields) -> None:
        if fields is None:
            return
        iid = str(fields.lot_id)
        item = None
        try:
            item = account.get_item(id=iid)
        except Exception as ex:
            logger.debug("save_lot get_item(%s): %s", iid, ex)

        if not fields.active:
            if iid not in account._fp_deact_backup and item is not None:
                account._fp_deact_backup[iid] = int(getattr(item, "price", 0) or 0)
            account._fp_soft_deactivated.add(iid)
            try:
                account.update_item(iid, price=DEACTIVATE_PRICE)
            except Exception as ex:
                logger.warning("save_lot deactivate %s: %s", iid, ex)
            _save_state(account)
            return

        if iid in account._fp_soft_deactivated:
            account._fp_soft_deactivated.discard(iid)
            restore_price = account._fp_deact_backup.pop(iid, None)
            if fields.price and float(fields.price) > 0:
                price = int(round(float(fields.price)))
            elif restore_price:
                price = int(restore_price)
            else:
                price = None
            try:
                if price is not None:
                    account.update_item(iid, price=price)
                if item is None:
                    item = account.get_item(id=iid)
                if item is not None and getattr(item, "status", None) != ItemStatuses.APPROVED:
                    _publish_default(account, iid, item)
            except Exception as ex:
                logger.warning("save_lot activate %s: %s", iid, ex)
            _save_state(account)
            return

        if fields.price is not None and float(fields.price) > 0:
            try:
                account.update_item(iid, price=int(round(float(fields.price))))
            except Exception as ex:
                logger.warning("save_lot price %s: %s", iid, ex)

    def get_my_subcategory_lots(sid):  # noqa: ARG001
        if not account.id:
            account.get()
        user = account.get_user(id=account.id)
        lots = []
        cursor = None
        statuses = [
            ItemStatuses.APPROVED,
            ItemStatuses.PENDING_MODERATION,
            ItemStatuses.PENDING_APPROVAL,
            ItemStatuses.DRAFT,
            ItemStatuses.EXPIRED,
        ]
        while True:
            page = user.get_items(count=24, statuses=statuses, after_cursor=cursor)
            for item in page.items:
                lots.append(
                    type(
                        "LotStub",
                        (),
                        {
                            "id": item.id,
                            "description": getattr(item, "name", "") or "",
                            "title": getattr(item, "name", "") or "",
                            "subcategory": SubCategoryStub(id=FP_SUBCATEGORY_ID),
                        },
                    )()
                )
            if not page.page_info.has_next_page:
                break
            cursor = page.page_info.end_cursor
        return lots

    account.get_subcategory = get_subcategory
    account.get_lot_fields = get_lot_fields
    account.save_lot = save_lot
    account.get_my_subcategory_lots = get_my_subcategory_lots
    account._fp_compat_applied = True

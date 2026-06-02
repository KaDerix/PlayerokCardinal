"""
Адаптер профиля лотов для Telegram-ПУ (совместимость с FunPay Cardinal API).
"""
from __future__ import annotations

from dataclasses import dataclass

from PlayerokAPI.enums import ItemStatuses


@dataclass
class SubCategoryStub:
    id: int | str
    name: str = ""


@dataclass
class LotShortcutStub:
    id: str | int
    description: str | None
    title: str | None
    price: float
    subcategory: SubCategoryStub | None = None


class PlayerokTGProfile:
    """Минимальная замена FunPay UserProfile для tg_profile / auto_delivery."""

    def __init__(self, lots: list[LotShortcutStub]):
        self._lots = lots
        self._by_subcategory: dict[SubCategoryStub, dict] = {}
        for lot in lots:
            sc = lot.subcategory or SubCategoryStub(id=0)
            self._by_subcategory.setdefault(sc, {})[lot.id] = lot

    def get_lots(self) -> list[LotShortcutStub]:
        return list(self._lots)

    def get_common_lots(self) -> list[LotShortcutStub]:
        return list(self._lots)

    def get_sorted_lots(self, mode: int):
        if mode == 2:
            return dict(self._by_subcategory)
        if mode == 1:
            return {lot.id: lot for lot in self._lots}
        return {}


def build_tg_profile(account) -> PlayerokTGProfile:
    if not account.id:
        account.get()
    user = account.get_user(id=account.id)
    lots: list[LotShortcutStub] = []
    cursor = None
    statuses = [
        ItemStatuses.APPROVED,
        ItemStatuses.PENDING_MODERATION,
        ItemStatuses.PENDING_APPROVAL,
        ItemStatuses.DRAFT,
    ]
    while True:
        page = user.get_items(count=24, statuses=statuses, after_cursor=cursor)
        for item in page.items:
            name = getattr(item, "name", "") or ""
            price = float(getattr(item, "price", 0) or 0)
            lots.append(
                LotShortcutStub(
                    id=item.id,
                    description=name,
                    title=name,
                    price=price,
                    subcategory=SubCategoryStub(id=0, name=""),
                )
            )
        if not page.page_info.has_next_page:
            break
        cursor = page.page_info.end_cursor
    return PlayerokTGProfile(lots)

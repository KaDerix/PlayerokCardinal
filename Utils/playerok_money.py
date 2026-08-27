"""Конвертация сумм Playerok (рубли в API)."""
from __future__ import annotations


def to_rub(amount) -> float:
    if amount is None:
        return 0.0
    try:
        return float(amount)
    except (TypeError, ValueError):
        return 0.0


def balance_display_rub(balance) -> tuple[float, float, float]:
    """Общий, доступно, заморожено/в ожидании для отображения."""
    if not balance:
        return 0.0, 0.0, 0.0
    total = to_rub(getattr(balance, "value", 0))
    available = to_rub(getattr(balance, "available", 0))
    frozen = to_rub(getattr(balance, "frozen", 0))
    pending = to_rub(getattr(balance, "pending_income", 0))
    if frozen <= 0:
        if pending > 0:
            frozen = pending
        elif total > available + 0.001:
            frozen = max(0.0, total - available)
    return total, available, frozen


def deal_order_price_rub(deal) -> float:
    """Цена лота для покупателя (item.price)."""
    if not deal:
        return 0.0
    item = getattr(deal, "item", None)
    if not item:
        return 0.0
    for attr in ("price", "raw_price"):
        val = getattr(item, attr, None)
        if val:
            return to_rub(val)
    return 0.0


def deal_seller_income_rub(deal) -> float:
    """Сумма продавца по сделке (transaction.value или цена минус комиссия)."""
    if not deal:
        return 0.0
    tx = getattr(deal, "transaction", None)
    if tx is not None and getattr(tx, "value", None) is not None:
        return to_rub(tx.value)
    price = deal_order_price_rub(deal)
    item = getattr(deal, "item", None)
    if item and price > 0:
        fee = getattr(item, "fee_multiplier", None)
        if fee is not None:
            try:
                return round(price * (1.0 - float(fee)), 2)
            except (TypeError, ValueError):
                pass
    return price

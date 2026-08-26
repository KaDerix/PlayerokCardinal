"""Синхронизация raw/list конфигов автовыдачи."""
from __future__ import annotations

import logging
import os
from configparser import ConfigParser
from typing import TYPE_CHECKING

from Utils import config_loader as cfg_loader

if TYPE_CHECKING:
    from cardinal import Cardinal

logger = logging.getLogger("POC.ad_config")

AD_CFG_PATH = "configs/auto_delivery.cfg"

DEFAULT_RESPONSE = (
    "Спасибо за покупку, $username!\n\n"
    "Вот твой товар:\n\n"
    "$product"
)


def goods_file_path(section) -> str | None:
    raw = section.get("goods_file") or section.get("productsFileName")
    if not raw:
        return None
    raw = raw.strip()
    if raw.startswith("storage/"):
        return raw
    return f"storage/products/{raw}"


def goods_file_basename(section) -> str | None:
    path = goods_file_path(section)
    if not path:
        return None
    return os.path.basename(path)


def migrate_section(section) -> None:
    gf = section.get("goods_file")
    legacy = section.get("productsFileName")
    if not gf and legacy:
        path = legacy if legacy.startswith("storage/") else f"storage/products/{legacy}"
        section["goods_file"] = path
        section.pop("productsFileName", None)
    elif gf and legacy:
        section.pop("productsFileName", None)


def migrate_raw_cfg(raw_cfg: ConfigParser) -> None:
    for name in raw_cfg.sections():
        if name.startswith("!"):
            continue
        migrate_section(raw_cfg[name])


def reload_ad_cfg(cardinal: Cardinal) -> None:
    cardinal.AD_CFG = cfg_loader.load_auto_delivery_config(AD_CFG_PATH)


def save_ad_cfg(cardinal: Cardinal) -> None:
    migrate_raw_cfg(cardinal.RAW_AD_CFG)
    cardinal.save_config(cardinal.RAW_AD_CFG, AD_CFG_PATH)
    reload_ad_cfg(cardinal)


def section_names(raw_cfg: ConfigParser) -> list[str]:
    return [s for s in raw_cfg.sections() if not s.startswith("!")]


def lot_bound(raw_cfg: ConfigParser, lot_id: str) -> str | None:
    for name in section_names(raw_cfg):
        if raw_cfg[name].get("lot_id", "").strip() == str(lot_id):
            return name
    return None


def find_profile_lot(cardinal: Cardinal, title: str):
    if not cardinal.tg_profile:
        return None
    title_lower = title.strip().lower()
    for lot in cardinal.tg_profile.get_common_lots():
        for candidate in (lot.title, lot.description):
            if candidate and candidate.strip().lower() == title_lower:
                return lot
    return None


def add_lot_section(cardinal: Cardinal, title: str, lot_id: str = "") -> str:
    raw = cardinal.RAW_AD_CFG
    if title not in raw.sections():
        raw.add_section(title)
    raw[title]["response"] = raw[title].get("response") or DEFAULT_RESPONSE
    if lot_id:
        raw[title]["lot_id"] = str(lot_id)
    save_ad_cfg(cardinal)
    return title

import configparser
from configparser import ConfigParser, SectionProxy
import codecs
import logging
import os

logger = logging.getLogger("POC.config_loader")

from Utils.exceptions import (ParamNotFoundError, EmptyValueError, ValueNotValidError, SectionNotFoundError,
                              ConfigParseError, ProductsFileNotFoundError, NoProductVarError,
                              SubCommandAlreadyExists, DuplicateSectionErrorWrapper)
from Utils.cardinal_tools import hash_password, OPTIONAL_MAIN_SECTIONS

def check_param(param_name: str, section: SectionProxy, valid_values: list[str | None] | None = None,
                raise_if_not_exists: bool = True) -> str | None:
    if param_name not in list(section.keys()):
        if raise_if_not_exists:
            raise ParamNotFoundError(param_name)
        return None

    value = section[param_name].strip()

    if not value:
        if valid_values and None in valid_values:
            return value
        raise EmptyValueError(param_name)

    if valid_values and valid_values != [None] and value not in valid_values:
        raise ValueNotValidError(param_name, value, valid_values)
    return value

def create_config_obj(config_path: str) -> ConfigParser:
    config = ConfigParser(delimiters=(":",), interpolation=None)
    config.optionxform = str
    config.read_file(codecs.open(config_path, "r", "utf8"))
    return config

def load_main_config(config_path: str):
    config = create_config_obj(config_path)
    values = {
        "Playerok": {
            "token": "any",
            "ddg5": "any+empty",
            "cookies": "any+empty",
            "user_agent": "any+empty",
            "autoResponse": ["0", "1"],
            "autoDelivery": ["0", "1"],
            "autoRestore": ["0", "1"],
            "multiDelivery": ["0", "1"],
            "autoDisable": ["0", "1"],
            "autoCompleteDeals": ["0", "1"],
            "autoWithdrawal": ["0", "1"],
            "restorePriorityMode": ["free", "premium"],
            "oldMsgGetMode": ["0", "1"],
            "keepSentMessagesUnread": ["0", "1"]
        },
        "Telegram": {
            "enabled": ["0", "1"],
            "token": "any+empty",
            "secretKeyHash": "any",
            "proxy": "any+empty",
            "blockLogin": ["0", "1"]
        },
        "Proxy": {
            "enable": ["0", "1"],
            "ip": "any+empty",
            "port": "any+empty",
            "login": "any+empty",
            "password": "any+empty",
            "check": ["0", "1"]
        },
        "Other": {
            "watermark": "any+empty",
            "requestsDelay": [str(i) for i in range(1, 101)],
            "language": ["ru", "en", "uk"]
        }
    }

    result = {}
    for section_name in values:
        if section_name not in config.sections():
            raise ConfigParseError(config_path, section_name, SectionNotFoundError())
        result[section_name] = {}
        section = config[section_name]

        for key in values[section_name]:
            valid_values = values[section_name][key]
            
            if section_name == "Playerok" and key == "oldMsgGetMode" and key not in section:
                config.set("Playerok", "oldMsgGetMode", "0")
                with open(config_path, "w", encoding="utf-8") as f:
                    config.write(f)
            elif section_name == "Playerok" and key == "keepSentMessagesUnread" and key not in section:
                config.set("Playerok", "keepSentMessagesUnread", "0")
                with open(config_path, "w", encoding="utf-8") as f:
                    config.write(f)
            elif section_name == "Playerok" and key == "restorePriorityMode" and key not in section:
                config.set("Playerok", "restorePriorityMode", "premium")
                with open(config_path, "w", encoding="utf-8") as f:
                    config.write(f)
            elif section_name == "Playerok" and key in (
                "multiDelivery", "autoDisable", "autoCompleteDeals", "autoWithdrawal"
            ) and key not in section:
                config.set("Playerok", key, "0")
                with open(config_path, "w", encoding="utf-8") as f:
                    config.write(f)
            elif section_name == "Other" and key == "language" and key not in section:
                config.set("Other", "language", "ru")
                with open(config_path, "w", encoding="utf-8") as f:
                    config.write(f)
            elif section_name == "Telegram" and key == "proxy" and key not in section:
                config.set("Telegram", "proxy", "")
                with open(config_path, "w", encoding="utf-8") as f:
                    config.write(f)
            elif section_name == "Playerok" and key in ("ddg5", "cookies") and key not in section:
                config.set("Playerok", key, "")
                with open(config_path, "w", encoding="utf-8") as f:
                    config.write(f)
            
            try:
                if valid_values == "any":
                    result[section_name][key] = check_param(key, section, None)
                elif valid_values == "any+empty":
                    result[section_name][key] = check_param(key, section, [None])
                else:
                    result[section_name][key] = check_param(key, section, valid_values)
            except (ParamNotFoundError, EmptyValueError, ValueNotValidError) as e:
                raise ConfigParseError(config_path, section_name, e)

    for section_name, defaults in OPTIONAL_MAIN_SECTIONS.items():
        if section_name not in config.sections():
            continue
        result[section_name] = {}
        section = config[section_name]
        for key, default in defaults.items():
            if key in section:
                result[section_name][key] = section[key].strip()
            else:
                result[section_name][key] = default

    return result

def load_auto_response_config(config_path: str):
    result = {}
    try:
        config = create_config_obj(config_path)
    except FileNotFoundError:
        return result
    except:
        raise

    for section_name in config.sections():
        # Пропускаем секции, начинающиеся с ! (комментарии/документация)
        if section_name.startswith("!"):
            continue
        section = config[section_name]
        try:
            command = check_param("command", section)
            response = check_param("response", section)
            result[section_name] = {"command": command, "response": response}
        except (ParamNotFoundError, EmptyValueError) as e:
            logger.warning(
                "Пропускаю секцию %r в %s: %s. Добавьте command: и response: или переименуйте секцию в !%s.",
                section_name,
                config_path,
                e,
                section_name.lstrip("!"),
            )
    return result

def load_raw_auto_response_config(config_path: str):
    try:
        config = create_config_obj(config_path)
        return config
    except FileNotFoundError:
        config = ConfigParser(delimiters=(":",), interpolation=None)
        config.optionxform = str
        return config

def load_raw_auto_delivery_config(config_path: str):
    try:
        config = create_config_obj(config_path)
        return config
    except FileNotFoundError:
        config = ConfigParser(delimiters=(":",), interpolation=None)
        config.optionxform = str
        return config


def _resolve_goods_file(section) -> str | None:
    raw = section.get("goods_file") or section.get("productsFileName")
    if not raw or not raw.strip():
        return None
    raw = raw.strip()
    if raw.startswith("storage/"):
        return raw
    return f"storage/products/{raw}"


def load_auto_delivery_config(config_path: str):
    result = []
    try:
        config = create_config_obj(config_path)
    except FileNotFoundError:
        return result
    except:
        raise

    for section_name in config.sections():
        if section_name.startswith("!"):
            continue
        section = config[section_name]
        lot_id = section.get("lot_id", "").strip()
        if not lot_id:
            logger.warning(
                "Пропускаю секцию %r в %s: не указан lot_id.",
                section_name, config_path,
            )
            continue

        goods_file = _resolve_goods_file(section)
        if not goods_file:
            logger.warning(
                "Пропускаю секцию %r в %s: не привязан goods_file.",
                section_name, config_path,
            )
            continue

        try:
            response = check_param("response", section)
        except (ParamNotFoundError, EmptyValueError) as e:
            logger.warning("Пропускаю секцию %r в %s: %s.", section_name, config_path, e)
            continue

        if not os.path.exists(goods_file):
            logger.warning(
                "Пропускаю секцию %r в %s: файл %r не найден.",
                section_name, config_path, goods_file,
            )
            continue

        if "$product" not in response:
            logger.warning(
                "Пропускаю секцию %r в %s: в response нет $product.",
                section_name, config_path,
            )
            continue

        entry = {
            "lot_id": lot_id,
            "goods_file": goods_file,
            "response": response,
        }
        for opt in ("disableMultiDelivery", "disableAutoDisable", "disableAutoRestore"):
            val = check_param(opt, section, valid_values=["0", "1"], raise_if_not_exists=False)
            if val is not None:
                entry[opt] = val
        result.append(entry)
    return result



"""Fix duplicated blocks in auto_steam_rent.py after initial patch."""
from pathlib import Path

P = Path(__file__).resolve().parents[1] / "plugins" / "auto_steam_rent.py"
lines = P.read_text(encoding="utf-8").splitlines(keepends=True)

# Remove duplicate block: broken _load_lot_templates + second copy of helpers/handlers
start = None
end = None
for i, line in enumerate(lines):
    if start is None and line.startswith("def _load_lot_templates()") and i > 4000:
        # first occurrence after BIND_TO should be kept; second is broken if followed by PENDING_RESTORE
        peek = "".join(lines[i : i + 8])
        if "except Exception:\n        \n\nPENDING_RESTORE" in peek or "except Exception:\n        \nPENDING_RESTORE" in peek:
            start = i
    if start is not None and line.startswith("LOT_TEMPLATES = []") and i > start + 5:
        end = i
        break

if start is not None and end is not None:
    fixed_load = [
        "def _load_lot_templates() -> None:\n",
        "    global LOT_TEMPLATES\n",
        "    try:\n",
        "        data = json.loads(LOTS_FILE.read_text(encoding=\"utf-8\"))\n",
        "        LOT_TEMPLATES = data.get(\"lots\", [])\n",
        "    except Exception:\n",
        "        LOT_TEMPLATES = []\n",
        "\n",
        "\n",
    ]
    lines = lines[:start] + fixed_load + lines[end:]

text = "".join(lines)

# Remove init manual handler registration
text = text.replace(
    "        handle_funpay_message.plugin_uuid = UUID\n"
    "        if handle_funpay_message not in CARDINAL.new_message_handlers:\n"
    "            CARDINAL.new_message_handlers.append(handle_funpay_message)\n"
    "            LOGGER.info(\"%s FunPay message handler registered successfully\", LOGGER_PREFIX)\n"
    "        else:\n"
    "            LOGGER.warning(\"%s FunPay message handler already registered\", LOGGER_PREFIX)\n\n"
    "        for lot in _load_lots():\n"
    "            lid = lot.get(\"lot_id\")\n"
    "            if lid:\n"
    "                try:\n"
    "                    restore_rent_lot_after_sale(CARDINAL, str(str(lid)))\n"
    "                except Exception as exc:\n"
    "                    LOGGER.warning(\"%s Initial stock sync for lot %s failed: %s\", LOGGER_PREFIX, lid, exc)\n\n",
    "",
)

# Remove dead feedback handlers using MessageTypes
import re
text = re.sub(
    r"def process_feedback_from_message\(cardinal, event: NewMessageEvent\) -> None:[\s\S]*?LOGGER\.error\(\"%s Feedback message handler error: %s\", LOGGER_PREFIX, exc, exc_info=True\)\n\n",
    "",
    text,
    count=1,
)
text = re.sub(
    r"def process_feedback\(cardinal, event\) -> None:[\s\S]*?LOGGER\.error\(\"%s Feedback handler error: %s\", LOGGER_PREFIX, exc, exc_info=True\)\n\n",
    "",
    text,
    count=1,
)

# Unify _send_chat_message: remove early duplicate (watermark version), enhance bottom one
text = re.sub(
    r"def _send_chat_message\(cardinal, chat_id: str \| int, message: str, \*, watermark: bool = True\) -> bool:[\s\S]*?return False\n\n\n",
    "",
    text,
    count=1,
)

old_send = '''def _send_chat_message(cardinal, chat_id: str | int, message: str, *, parse_mode: Optional[str] = None) -> bool:
           
    try:
        LOGGER.debug(
            "%s Attempting to send Playerok message: chat=%s, message_len=%d, preview=%r",
            LOGGER_PREFIX,
            chat_id,
            len(message),
            message[:100],
        )
        cardinal.send_message(int(chat_id), message)
        LOGGER.info("%s Successfully sent Playerok message to chat %s", LOGGER_PREFIX, chat_id)
        return True
    except Exception as exc:
        LOGGER.error(
            "%s Failed to send Playerok message to %s: %s (message was: %r)",
            LOGGER_PREFIX,
            chat_id,
            exc,
            message[:200],
            exc_info=True
        )
        return False'''

new_send = '''def _send_chat_message(cardinal, chat_id: str | int, message: str, *, watermark: bool = True, parse_mode: Optional[str] = None) -> bool:
    try:
        LOGGER.debug(
            "%s Attempting to send Playerok message: chat=%s, message_len=%d, preview=%r",
            LOGGER_PREFIX,
            chat_id,
            len(message),
            message[:100],
        )
        if hasattr(cardinal, "send_message"):
            if watermark:
                cardinal.send_message(int(chat_id), message)
            else:
                try:
                    cardinal.account.send_message(
                        str(chat_id),
                        message,
                        mark_chat_as_read=not getattr(cardinal, "keep_sent_messages_unread", False),
                    )
                except Exception:
                    cardinal.send_message(int(chat_id), message)
        LOGGER.info("%s Successfully sent Playerok message to chat %s", LOGGER_PREFIX, chat_id)
        return True
    except Exception as exc:
        LOGGER.error(
            "%s Failed to send Playerok message to %s: %s (message was: %r)",
            LOGGER_PREFIX,
            chat_id,
            exc,
            message[:200],
            exc_info=True,
        )
        return False'''

text = text.replace(old_send, new_send)

# UI strings
text = text.replace("В этом чате FunPay", "В этом чате Playerok")
text = text.replace("Sending guard code to FunPay chat", "Sending guard code to Playerok chat")
text = text.replace("%s FunPay message:", "%s Playerok message:")

# Settings menu for restore - add callback handlers if missing; search settings section
text = text.replace("restore_rent_lot_after_sale(CARDINAL, str(str(", "restore_rent_lot_after_sale(CARDINAL, str(")

P.write_text(text, encoding="utf-8")
print("Cleanup done", P)

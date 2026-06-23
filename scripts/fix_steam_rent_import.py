"""Fix auto_steam_rent.py: metadata first, optional steam stack."""
from pathlib import Path

SRC = Path(r"C:\Users\iegor\Desktop\auto_steam_rent.py")
DST = Path(__file__).resolve().parents[1] / "plugins" / "auto_steam_rent.py"
text = SRC.read_text(encoding="utf-8")

# Remove duplicate metadata block later in file
import re

text = re.sub(
    r"\nNAME = \"Auto Steam Rent\"\nVERSION = \"1\.0\.0-playerok\"\n"
    r"DESCRIPTION = \"Автоаренда Steam-аккаунтов на Playerok\"\n"
    r"CREDITS = \"@embedium / @KaDerix\"\n"
    r"UUID = \"[^\"]+\"\nSETTINGS_PAGE = False\n\n",
    "\n",
    text,
    count=1,
)

# Find steam class block
start = text.index("class ErrorSteamPasswordChange(Exception):")
end = text.index("\ndef generate_guard_code(")

steam_block = text[start:end]
rest = text[end:]
prefix_raw = text[: text.index("class ErrorSteamPasswordChange(Exception):")]

# Remove old auto-install invocation and steam imports from prefix
prefix_raw = re.sub(
    r"# Запускаем проверку зависимостей\n_check_and_install_deps\(\)\n\n# Теперь импортируем все зависимости\n"
    r"import aiohttp\nimport pydantic\nimport rsa\n"
    r"from lxml\.html import document_fromstring\n"
    r"from pysteamauth\.abstract import CookieStorageAbstract, RequestStrategyAbstract\n"
    r"from pysteamauth\.auth import Steam\n"
    r"from steamlib\.api\.trade import SteamTrade\n"
    r"from steamlib\.api\.trade\.exceptions import NotFoundMobileConfirmationError\n",
    "",
    prefix_raw,
    count=1,
)

# Fix emoji prints in installer
for old, new in [
    ('print(f"✅ {package} установлен")', 'print(f"[OK] {package}")'),
    ('print(f"❌ Ошибка установки {package}: {e}")', 'print(f"[ERR] install {package}: {e}")'),
    ('print(f"✅ {package} установлен (альтернативный способ)")', 'print(f"[OK] {package} user install")'),
    ('print(f"⚠️ Не удалось установить {package}, продолжаем...")', 'print(f"[WARN] skip {package}")'),
    ('print("✅ steamlib установлен")', 'print("[OK] steamlib")'),
    ('print("✅ steamlib установлен (с флагами)")', 'print("[OK] steamlib flags")'),
    ('print("❌ Критическая ошибка: не удалось установить steamlib")', 'print("[ERR] steamlib failed")'),
    ('print("✅ Все зависимости успешно установлены!")', 'print("[OK] all deps installed")'),
    ('print(f"⚠️ Не удалось установить: {still_missing}")', 'print(f"[WARN] still missing: {still_missing}")'),
    ('print("⚠️ Не удалось установить steamlib, пробуем с флагами...")', 'print("[WARN] steamlib retry")'),
]:
    prefix_raw = prefix_raw.replace(old, new)

header = '''"""Auto Steam Rent — Playerok Cardinal plugin."""

NAME = "Auto Steam Rent"
VERSION = "1.0.0-playerok"
DESCRIPTION = "Автоаренда Steam-аккаунтов на Playerok"
CREDITS = "@embedium / @KaDerix"
UUID = "029b4dd2-7111-4063-9fb0-6f83c8727f61"
SETTINGS_PAGE = False

STEAM_LIBS_AVAILABLE = False
STEAM_IMPORT_ERROR = ""

'''

# Keep auto-install helpers but remove leading comment-only first line duplication
if prefix_raw.startswith("# ========= AUTO-INSTALL"):
    install_part = prefix_raw
else:
    install_part = prefix_raw

# Ensure telebot + stdlib imports remain; insert bootstrap before steam classes
bootstrap = '''
def _bootstrap_steam_stack() -> bool:
    """Import/install Steam libraries without breaking plugin registration."""
    global STEAM_LIBS_AVAILABLE, STEAM_IMPORT_ERROR
    if STEAM_LIBS_AVAILABLE:
        return True
    try:
        _check_and_install_deps()
        import aiohttp  # noqa: F401
        import pydantic  # noqa: F401
        import rsa  # noqa: F401
        from lxml.html import document_fromstring  # noqa: F401
        from pysteamauth.abstract import CookieStorageAbstract, RequestStrategyAbstract  # noqa: F401
        from pysteamauth.auth import Steam  # noqa: F401
        from steamlib.api.trade import SteamTrade  # noqa: F401
        from steamlib.api.trade.exceptions import NotFoundMobileConfirmationError  # noqa: F401
        STEAM_LIBS_AVAILABLE = True
        STEAM_IMPORT_ERROR = ""
        return True
    except Exception as exc:
        STEAM_IMPORT_ERROR = str(exc)
        STEAM_LIBS_AVAILABLE = False
        return False


'''

stubs = '''
class ErrorSteamPasswordChange(Exception):
    pass


class CustomSteam:
    def __init__(self, *args, **kwargs):
        raise ErrorSteamPasswordChange(STEAM_IMPORT_ERROR or "Steam libraries not installed")


class SteamPasswordChange:
    def __init__(self, *args, **kwargs):
        raise ErrorSteamPasswordChange(STEAM_IMPORT_ERROR or "Steam libraries not installed")


class NotFoundMobileConfirmationError(Exception):
    pass


'''

# prefix up to ErrorSteamPasswordChange - strip install section start duplicate header
idx = install_part.find("class ErrorSteamPasswordChange")
if idx != -1:
    install_part = install_part[:idx]

# Remove duplicate metadata if still at start of install_part after header merge
install_part = re.sub(
    r'^"""Auto Steam Rent.*?SETTINGS_PAGE = False\n\n',
    '',
    install_part,
    count=1,
    flags=re.S,
)

new_text = header + install_part + bootstrap
if True:
    new_text += "if _bootstrap_steam_stack():\n"
    for line in steam_block.splitlines():
        new_text += ("    " + line + "\n") if line.strip() else "\n"
    new_text += "else:\n"
    for line in stubs.splitlines():
        new_text += ("    " + line + "\n") if line.strip() else "\n"

new_text += rest

# init_plugin: log steam status
new_text = new_text.replace(
    '    LOGGER.info("%s Plugin init", LOGGER_PREFIX)',
    '    LOGGER.info("%s Plugin init (steam_libs=%s)", LOGGER_PREFIX, STEAM_LIBS_AVAILABLE)\n'
    '    if not STEAM_LIBS_AVAILABLE:\n'
    '        LOGGER.warning("%s Steam libs unavailable: %s — Guard/password change disabled until installed", LOGGER_PREFIX, STEAM_IMPORT_ERROR)',
)

# _rotate_password guard
new_text = new_text.replace(
    "async def _rotate_password(account: Dict[str, Any]) -> Optional[str]:\n    mafile = account.get(\"mafile\") or {}",
    "async def _rotate_password(account: Dict[str, Any]) -> Optional[str]:\n    if not STEAM_LIBS_AVAILABLE:\n        _bootstrap_steam_stack()\n    if not STEAM_LIBS_AVAILABLE:\n        LOGGER.warning(\"%s Password rotate skipped: steam libs unavailable\", LOGGER_PREFIX)\n        return None\n    mafile = account.get(\"mafile\") or {}",
)

DST.parent.mkdir(parents=True, exist_ok=True)
DST.write_text(new_text, encoding="utf-8")
print("Wrote", DST, "lines", len(new_text.splitlines()))

_R = "\033[0m"
_B = "\033[1m"

B1 = "\033[38;5;27m"
B2 = "\033[38;5;33m"
B3 = "\033[38;5;39m"
B4 = "\033[38;5;45m"
B5 = "\033[38;5;51m"
W  = "\033[38;5;255m"
D  = "\033[38;5;245m"
F  = "\033[38;5;238m"

W_INNER = 50


def _osc_link(url: str, text: str) -> str:
    return f"\033]8;;{url}\033\\{text}\033]8;;\033\\"


def _row(visible: str, display: str | None = None) -> str:
    content = display if display is not None else visible
    pad = max(0, W_INNER - len(visible))
    left = pad // 2
    right = pad - left
    return f"{B1}║{_R}{' ' * left}{content}{' ' * right}{B1}║{_R}"


def build_banner(version: str) -> str:
    title_v = "PLAYEROK  CARDINAL"
    title_d = f"{W}{_B}PLAYEROK{_R}  {B5}{_B}CARDINAL{_R}"

    tag_v = "автоматизация  playerok.com"
    tag_d = f"{D}автоматизация{_R}  {B3}{_B}playerok.com{_R}"

    accent_v = "* . . . . . . . . . . . . . . *"
    accent_d = f"{B2}*{_R} {F}. . . . . . . . . . . . . .{_R} {B2}*{_R}"

    ver_v = f"v{version}"
    ver_d = f"{B4}{_B}v{version}{_R}"

    gh_v = "github.com/KaDerix/PlayerokCardinal"
    gh_d = _osc_link(
        "https://github.com/KaDerix/PlayerokCardinal",
        f"{D}{gh_v}{_R}",
    )

    tg_v = "t.me/KaDerix"
    tg_d = _osc_link("https://t.me/KaDerix", f"{B4}{tg_v}{_R}")

    return "\n".join([
        "",
        f"{B1}╔{'═' * W_INNER}╗{_R}",
        _row(""),
        _row(title_v, title_d),
        _row(tag_v, tag_d),
        _row(accent_v, accent_d),
        f"{B2}╠{'─' * W_INNER}╣{_R}",
        _row(""),
        _row(ver_v, ver_d),
        _row(gh_v, gh_d),
        _row(tg_v, tg_d),
        _row(""),
        f"{B1}╚{'═' * W_INNER}╝{_R}",
        "",
    ])

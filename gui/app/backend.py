# =============================================================================
# Бэкенд GUI — общий интерфейс (Windows-реализация + mock для разработки)
# =============================================================================

import json
import re
import sys
import ctypes
from pathlib import Path

APP_VERSION = "0.1.7"
GITHUB_REPO = "SkilinPur/zapret-GUI-Windows"
GITHUB_URL = f"https://github.com/{GITHUB_REPO}"
STRATEGIES_REPO = "Flowseal/zapret-discord-youtube"
CORE_REPO = "bol-van/zapret"


def app_root() -> Path:
    """Корень приложения: рядом с exe (сборка) или корень репозитория (dev)."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent.parent


def is_admin() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return True  # на Linux (dev) считаем админом


class Backend:
    """Интерфейс. Методы, которые GUI вызывает из вкладок.

    Долгие операции синхронные; вкладки запускают их в JobThread и передают
    callable `log(line)` для вывода.
    """

    name = "base"

    # --- пути и конфиг ---
    root: Path
    strategies_dir: Path
    bin_dir: Path

    def read_config(self) -> dict: ...
    def save_strategy(self, name: str, log=None) -> bool: ...
    def strategies(self): ...
    def strategy_description(self, name: str) -> str: ...

    # --- ядро (winws) ---
    def core_installed(self) -> str: ...          # версия или ""
    def core_latest(self) -> str: ...
    def download_core(self, log=None) -> bool: ...

    # --- стратегии ---
    def strategies_installed(self) -> str: ...    # хеш/маркер или ""
    def strategies_latest(self) -> str: ...
    def download_strategies(self, log=None) -> bool: ...

    # --- программа ---
    def program_latest(self): ...                 # (tag, notes) или ("", "")
    def update_program(self, log=None) -> bool: ...

    # --- запуск/остановка ---
    def state(self) -> bool: ...
    def start(self, strategy: str, log=None) -> bool: ...
    def stop(self, log=None) -> bool: ...

    # --- автозапуск (планировщик) ---
    def autostart_state(self) -> str: ...         # "on" | "off" | ""
    def autostart(self, enable: bool, log=None) -> bool: ...


# ---------------------------------------------------------------------------
# Авто-описание стратегии (из .bat), общее для всех платформ
# ---------------------------------------------------------------------------

def strategy_description_from_bat(path: Path, name: str) -> str:
    try:
        text = path.read_text(encoding="utf-8", errors="replace").lower()
    except Exception:
        return ""
    text = text.replace("\r", "")

    scope = " " + name.lower()
    for m in re.finditer(r'--hostlist=?["\']?%LISTS%([\w.-]+\.txt)', text):
        scope += " " + m.group(1)
    for m in re.finditer(r"--hostlist-domains=([\w.,-]+)", text):
        scope += " " + m.group(1)

    targets = []
    for key, label in (("google", "YouTube/Google"), ("googlevideo", "YouTube/Google"),
                       ("discord", "Discord"), ("rutube", "RuTube"),
                       ("4pda", "4PDA"), ("steam", "Steam"), ("vk", "VK"),
                       ("minecraft", "Minecraft"), ("hypixel", "Hypixel")):
        if key in scope and label not in targets:
            targets.append(label)
    if not targets and "general" in scope:
        targets.append("YouTube/Discord (основной список)")
    if "ipset-all" in text:
        targets.append("весь трафик")
    if not targets:
        targets.append("по спискам/хостам")

    def ports(marker):
        vals = []
        for m in re.finditer(rf"{marker}=([0-9,\-%]+)", text):
            for chunk in m.group(1).split(","):
                chunk = chunk.strip().strip("%")
                if not re.fullmatch(r"\d+(-\d+)?", chunk) or chunk in vals:
                    continue
                vals.append(chunk)
        return vals

    tcp, udp = ports(r"--filter-tcp"), ports(r"--filter-udp")
    modes = set()
    for m in re.finditer(r"--dpi-desync=([a-z0-9,_]+)", text):
        modes.update(x for x in m.group(1).split(",") if x)
    mode_map = {"fake": "fake (подмена ответа)", "fakedsplit": "fakedsplit",
                "multisplit": "multisplit (дробление)", "syndata": "syndata",
                "hostfakesplit": "hostfakesplit"}
    mode_labels = [mode_map.get(x, x) for x in sorted(modes)]
    if "autottl" in text:
        mode_labels.append("autottl")

    parts = []
    proto = []
    if tcp:
        proto.append("TCP " + ",".join(tcp))
    if udp:
        proto.append("UDP " + ",".join(udp))
    if proto:
        parts.append("; ".join(proto))
    if "fake-quic" in text or "fake-unknown-udp" in text:
        parts.append("подмена QUIC (UDP 443)")
    if "fake-discord" in text or "fake-stun" in text:
        parts.append("подмена Discord/STUN")
    if "fake-tls" in text:
        parts.append("подмена TLS")
    if mode_labels:
        parts.append("метод: " + ", ".join(mode_labels))

    lines = [f"Область: {' · '.join(targets)}."]
    if parts:
        lines.append(" ".join(parts) + ".")
    reps = set(re.findall(r"--dpi-desync-repeats=(\d+)", text))
    if reps:
        lines.append(f"Повторов пакета: {', '.join(sorted(reps))}.")
    return "\n".join(lines)


def write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def restart_self() -> None:
    """Перезапуск текущего python-процесса."""
    import os
    os.execv(sys.executable, [sys.executable, "-m", "gui.app.main"])

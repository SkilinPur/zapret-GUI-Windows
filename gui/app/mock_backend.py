# =============================================================================
# Mock-бэкенд — разработка GUI на Linux (winws тут не запустить)
# =============================================================================

import time
from pathlib import Path

from .backend import Backend, app_root


class MockBackend(Backend):
    name = "mock"

    def __init__(self):
        self.root = app_root()
        self.strategies_dir = self.root / "strategies"
        self.bin_dir = self.root / "bin"
        self._running = False
        self._log = None
        self._mock_strategies = ["general.bat", "general_alt.bat", "discord.bat"]
        self._mock_desc = {
            "general.bat": "Область: YouTube/Discord (основной список). TCP 80,443; UDP 443. Метод: fake.",
            "general_alt.bat": "Область: YouTube/Discord. TCP 80,443; UDP 443. Метод: multisplit (дробление).",
            "discord.bat": "Область: Discord · весь трафик. TCP 443; UDP 443 + Discord. Подмена Discord/STUN.",
        }

    def _emit(self, line):
        if self._log:
            self._log(line)

    def read_config(self):
        from .backend import read_json
        return read_json(self.root / "config.json")

    def save_strategy(self, name, log=None):
        from .backend import write_json
        if name not in self.strategies():
            return False
        cfg = self.read_config()
        cfg["strategy"] = name
        write_json(self.root / "config.json", cfg)
        return True

    def strategies(self):
        return list(self._mock_strategies)

    def strategy_description(self, name):
        return self._mock_desc.get(name, "")

    def game_filter_state(self):
        return getattr(self, "_gf", "off")

    def set_game_filter(self, mode):
        self._gf = mode
        return True

    def ipset_state(self):
        return getattr(self, "_ipset", "any")

    def set_ipset(self, mode):
        self._ipset = mode
        return True

    def core_installed(self):
        return "v72.13 (mock)"

    def core_latest(self):
        return ""

    def download_core(self, log=None):
        if log:
            log("> mock: ядро скачано")
        return True

    def strategies_installed(self):
        return "abcdef0123"

    def strategies_latest(self):
        return ""

    def download_strategies(self, log=None):
        if log:
            log("> mock: стратегии обновлены")
        return True

    def program_latest(self):
        return "", ""

    def update_program(self, log=None):
        if log:
            log("> mock: программа обновлена")
        return True

    def state(self):
        return self._running

    def start(self, strategy, log=None):
        self._log = log
        self._running = True
        self._emit(f"> mock: запуск обхода ({strategy})")
        return True

    def explain(self, log=None):
        return False

    def stop(self, log=None):
        self._log = log
        self._running = False
        self._emit("> mock: остановлен")
        return True

    def autostart_state(self):
        return "off"

    def autostart(self, enable, log=None):
        if log:
            log(f"> mock: автозапуск {'включён' if enable else 'выключен'}")
        return True

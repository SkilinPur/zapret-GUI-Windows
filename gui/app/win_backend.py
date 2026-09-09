# =============================================================================
# Windows-бэкенд: GUI-обёртка над пакетом Flowseal/zapret-discord-youtube
#
# Пакет Flowseal (релиз) самодостаточен: .bat-стратегии + lists/ + bin/
# (winws.exe, WinDivert, шаблоны). Мы качаем релиз и раскладываем его в
# engine/ — как Linux-GUI оборачивает порт. Всё остальное (запуск winws,
# статус, автозапуск) — вокруг этого пакета.
# =============================================================================

import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.request
import zipfile
from pathlib import Path

from .backend import (
    APP_VERSION, Backend, STRATEGIES_REPO, app_root, read_json,
    strategy_description_from_bat, write_json,
)

CREATE_NO_WINDOW = 0x08000000
_AUTH_HEADERS = {"User-Agent": f"zapret-gui/{APP_VERSION}"}
CONFIG_NAME = "config.json"
ENGINE_MARK = ".engine-version"
LOG_TAIL = 12


def _http_json(url):
    req = urllib.request.Request(url, headers=_AUTH_HEADERS)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8", "replace"))


def _tail(path: Path, n: int = LOG_TAIL):
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except Exception:
        return []
    return lines[-n:]


class WinBackend(Backend):
    name = "windows"

    def __init__(self):
        self.root = app_root()
        self.engine = self.root / "engine"          # распакованный пакет Flowseal
        self.config_file = self.root / CONFIG_NAME
        self.logs_dir = self.root / "logs"
        self._proc_infos = []      # [{proc, log}]
        self._log = lambda _line: None
        self._task_cache = {}      # имя -> (время, bool)
        self._core_cache = (0.0, "")

    # ------------------------------------------------------------- пути

    def _winws(self) -> Path:
        return self.engine / "bin" / "winws.exe"

    def _emit(self, line):
        if self._log:
            self._log(line)

    # ------------------------------------------------------------- конфиг

    def read_config(self) -> dict:
        return read_json(self.config_file)

    def save_strategy(self, name: str, log=None) -> bool:
        if name not in self.strategies():
            if log:
                log(f"! стратегия не найдена: {name}")
            return False
        cfg = self.read_config()
        cfg["strategy"] = name
        try:
            write_json(self.config_file, cfg)
            if log:
                log(f"> способ сохранён: {name}")
            return True
        except Exception as exc:
            if log:
                log(f"! не удалось сохранить: {exc}")
            return False

    # ------------------------------------------------------------- стратегии

    def strategies(self):
        if not self.engine.is_dir():
            return []
        names = sorted(f.name for f in self.engine.glob("*.bat"))
        names.sort(key=lambda n: (n.lower() != "general.bat", n.lower()))
        return names

    def strategy_description(self, name: str) -> str:
        p = self.engine / name
        return strategy_description_from_bat(p, name) if p.exists() else ""

    # ------------------------------------------------------------- фильтры пакета

    def _lists(self) -> Path:
        return self.engine / "lists"

    def _utils(self) -> Path:
        return self.engine / "utils"

    def game_filter_state(self) -> str:
        """off | all | tcp | udp (как у Flowseal: utils/game_filter.enabled)."""
        f = self._utils() / "game_filter.enabled"
        try:
            if not f.exists():
                return "off"
            val = f.read_text(encoding="utf-8", errors="replace").strip().lower()
            return val if val in ("all", "tcp", "udp") else "off"
        except Exception:
            return "off"

    def set_game_filter(self, mode: str) -> bool:
        """mode: off | all | tcp | udp."""
        if mode not in ("off", "all", "tcp", "udp"):
            return False
        try:
            utils = self._utils()
            utils.mkdir(parents=True, exist_ok=True)
            f = utils / "game_filter.enabled"
            if mode == "off":
                f.unlink(missing_ok=True)
            else:
                f.write_text(mode + "\n", encoding="utf-8")
            return True
        except Exception:
            return False

    def ipset_state(self) -> str:
        """any | none | loaded."""
        f = self._lists() / "ipset-all.txt"
        try:
            if not f.exists():
                return "any"
            content = f.read_text(encoding="utf-8", errors="replace")
            if not content.strip():
                return "any"
            if "203.0.113.113/32" in content:
                return "none"
            return "loaded"
        except Exception:
            return "any"

    def set_ipset(self, mode: str) -> bool:
        """mode: any | none | loaded (по схеме service.bat ipset_switch)."""
        if mode not in ("any", "none", "loaded"):
            return False
        marker = "203.0.113.113/32\n"
        try:
            lists_dir = self._lists()
            lists_dir.mkdir(parents=True, exist_ok=True)
            f = lists_dir / "ipset-all.txt"
            backup = lists_dir / "ipset-all.txt.backup"
            if mode == "none":
                if not backup.exists() and f.exists():
                    f.rename(backup)
                f.write_text(marker, encoding="utf-8")
            elif mode == "any":
                f.write_text("", encoding="utf-8")
            else:  # loaded
                if backup.exists():
                    f.write_bytes(backup.read_bytes())
                elif not f.exists():
                    f.write_text("", encoding="utf-8")
            return True
        except Exception:
            return False

    # ------------------------------------------------------------- пакет Flowseal

    @staticmethod
    def _latest_tag():
        try:
            data = _http_json(f"https://api.github.com/repos/{STRATEGIES_REPO}/releases/latest")
            return data.get("tag_name", "") or ""
        except Exception:
            return ""

    def _install_package(self, log=None) -> bool:
        """Качает последний релиз Flowseal и раскладывает в engine/."""
        tag = self._latest_tag()
        if not tag:
            if log:
                log("! не удалось определить версию пакета Flowseal")
            return False
        url = (f"https://github.com/{STRATEGIES_REPO}/releases/download/"
               f"{tag}/zapret-discord-youtube-{tag}.zip")
        zpath = self.root / ".engine.zip"
        if log:
            log(f"> скачивание пакета Flowseal {tag}…")
        try:
            req = urllib.request.Request(url, headers=_AUTH_HEADERS)
            with urllib.request.urlopen(req, timeout=180) as resp:
                zpath.write_bytes(resp.read())
        except Exception as exc:
            if log:
                log(f"! ошибка скачивания: {exc}")
            return False

        tmp = self.root / ".engine-src"
        if tmp.exists():
            shutil.rmtree(tmp, ignore_errors=True)
        tmp.mkdir()
        try:
            with zipfile.ZipFile(zpath) as z:
                z.extractall(tmp)
        except Exception as exc:
            if log:
                log(f"! ошибка распаковки: {exc}")
            shutil.rmtree(tmp, ignore_errors=True)
            return False

        src = next((p for p in tmp.iterdir() if p.is_dir()), None)
        if src is None:
            if log:
                log("! в архиве пакета нет содержимого")
            shutil.rmtree(tmp, ignore_errors=True)
            return False

        old = self.root / ".engine-old"
        if self.engine.exists():
            if old.exists():
                shutil.rmtree(old, ignore_errors=True)
            self.engine.rename(old)
        try:
            src.rename(self.engine)
        except Exception as exc:
            if old.exists():
                old.rename(self.engine)
            if log:
                log(f"! не удалось разложить пакет: {exc}")
            shutil.rmtree(tmp, ignore_errors=True)
            return False
        if old.exists():
            shutil.rmtree(old, ignore_errors=True)
        shutil.rmtree(tmp, ignore_errors=True)
        (self.root / ENGINE_MARK).write_text(tag, encoding="utf-8")
        if log:
            log(f"> пакет Flowseal {tag} установлен в engine/")
        return True

    def strategies_installed(self) -> str:
        m = self.root / ENGINE_MARK
        return m.read_text(encoding="utf-8").strip() if m.exists() else ""

    def strategies_latest(self) -> str:
        return self._latest_tag()

    def download_strategies(self, log=None) -> bool:
        self._log = log
        return self._install_package(log)

    # ------------------------------------------------------------- ядро (в пакете)

    def core_installed(self) -> str:
        now = time.monotonic()
        if now - self._core_cache[0] < 30 and self._core_cache[1]:
            return self._core_cache[1]
        if not self._winws().exists():
            return ""
        ver = ""
        try:
            p = subprocess.run([str(self._winws()), "--version"], capture_output=True,
                               text=True, timeout=8, errors="replace",
                               creationflags=CREATE_NO_WINDOW)
            out = (p.stdout or "") + (p.stderr or "")
            ver = next((ln.strip() for ln in out.splitlines()
                        if "version" in ln.lower()), "")
        except Exception:
            pass
        tag = self.strategies_installed()
        result = ver or (f"Flowseal {tag}" if tag else "установлено")
        self._core_cache = (now, result)
        return result

    def core_latest(self) -> str:
        return ""

    def download_core(self, log=None) -> bool:
        self._log = log
        # winws+WinDivert входят в пакет Flowseal — ставим тем же пакетом
        return self._install_package(log)

    # ------------------------------------------------------------- программа

    def program_latest(self):
        try:
            data = _http_json("https://api.github.com/repos/SkilinPur/zapret-GUI-Windows/releases/latest")
            return (data.get("tag_name", "") or ""), (data.get("body", "") or "")
        except Exception:
            return "", ""

    def update_program(self, log=None) -> bool:
        if log:
            log("> самообновление программы появится позже. Открываю страницу релизов…")
        try:
            import webbrowser
            webbrowser.open("https://github.com/SkilinPur/zapret-GUI-Windows/releases/latest")
        except Exception:
            pass
        return False

    # ------------------------------------------------------------- запуск winws

    def _tasklist(self, image: str, ttl: float = 1.0) -> bool:
        """Проверка процесса через tasklist с коротким кэшем (не грузим UI)."""
        now = time.monotonic()
        hit = self._task_cache.get(image)
        if hit and now - hit[0] < ttl:
            return hit[1]
        res = False
        if os.name == "nt":
            try:
                p = subprocess.run(
                    ["tasklist", "/FI", f"IMAGENAME eq {image}"],
                    capture_output=True, text=True, timeout=8,
                    creationflags=CREATE_NO_WINDOW,
                )
                res = image in (p.stdout or "")
            except Exception:
                res = False
        self._task_cache[image] = (now, res)
        return res

    def state(self) -> bool:
        if any(i["proc"].poll() is None for i in self._proc_infos):
            return True
        return self._tasklist("winws.exe")

    def explain(self, log=None):
        reported = False
        for info in self._proc_infos:
            proc, path = info["proc"], info["log"]
            if info.get("acked"):
                continue
            if proc.poll() is None:
                continue
            info["acked"] = True
            reported = True
            if log:
                log(f"! winws завершился сам (код выхода: {proc.returncode})")
                log(f"! лог: {path}")
                for line in _tail(path):
                    log("    " + line)
        return reported

    def _runner(self, strategy: str) -> Path:
        """Готовит копию .bat, которая запускает winws в «фоне» (без start /min
        и лишних вызовов service.bat), в той же папке engine (чтобы %~dp0,
        %BIN%/%LISTS% и user-списки работали как в оригинале)."""
        src = self.engine / strategy
        raw = src.read_text(encoding="utf-8", errors="replace")
        text = raw.replace("\r", "")
        # Убираем не нужные нам вызовы (проверки/обновления самих себя)
        for call in ("call service.bat status_zapret", "call service.bat check_updates"):
            text = re.sub(rf"(?m)^\s*{re.escape(call)}\s*$", "", text)
        # winws запускаем в текущей консоли, а не через start /min
        text = re.sub(r"^[^\n]*?\bwinws\.exe\"", '"%BIN%winws.exe"', text, count=1,
                      flags=re.M)
        slug = re.sub(r"[^\w\-]+", "_", Path(strategy).stem).strip("_") or "strat"
        runner = self.engine / f".gui-{slug}.bat"
        runner.write_text(text.replace("\n", "\r\n"), encoding="utf-8")
        return runner

    def start(self, strategy: str, log=None) -> bool:
        self._log = log
        if self.state():
            self._emit("! обход уже запущен")
            return False
        w = self._winws()
        if not w.exists():
            self._emit("! пакет не установлен — откройте «Обновление» и скачайте ядро/стратегии")
            return False
        bat = self.engine / strategy
        if not bat.exists():
            self._emit(f"! стратегия не найдена: {strategy}")
            return False

        try:
            runner = self._runner(strategy)
        except Exception as exc:
            self._emit(f"! не удалось подготовить запуск: {exc}")
            return False

        self.logs_dir.mkdir(exist_ok=True)
        stamp = time.strftime("%Y%m%d-%H%M%S")
        logpath = self.logs_dir / f"winws-{stamp}.log"
        try:
            fh = open(logpath, "a", encoding="utf-8", errors="replace")
        except Exception as exc:
            self._emit(f"! не открыть лог {logpath}: {exc}")
            return False

        self._proc_infos = []
        self._emit(f"> запуск обхода ({strategy})…")
        try:
            proc = subprocess.Popen(
                ["cmd", "/c", str(runner)],
                cwd=str(self.engine),
                stdout=fh, stderr=subprocess.STDOUT,
                creationflags=CREATE_NO_WINDOW,
            )
        except Exception as exc:
            fh.close()
            self._emit(f"! ошибка запуска: {exc}")
            return False
        self._proc_infos.append({"proc": proc, "log": logpath,
                                 "runner": runner, "acked": False})
        self._emit(f"> запущено (pid {proc.pid}) — лог: {logpath.name}")
        return self.state()

    def stop(self, log=None) -> bool:
        self._log = log
        self._emit("> остановка обхода")
        for info in self._proc_infos:
            info["acked"] = True
            proc = info["proc"]
            pid = proc.pid if proc.pid else 0
            if proc.poll() is None and os.name == "nt" and pid:
                # убиваем всё дерево, запущенное через cmd (в т.ч. winws-потомка)
                subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"],
                               capture_output=True, text=True, timeout=15,
                               creationflags=CREATE_NO_WINDOW)
            if proc.poll() is None:
                try:
                    proc.terminate()
                except Exception:
                    pass
            runner = info.get("runner")
            if runner and runner.exists():
                try:
                    runner.unlink()
                except Exception:
                    pass
        self._proc_infos = []
        if os.name == "nt":
            subprocess.run(["taskkill", "/F", "/IM", "winws.exe"],
                           capture_output=True, text=True, timeout=15,
                           creationflags=CREATE_NO_WINDOW)
        self._task_cache.pop("winws.exe", None)
        self._emit("> проверка остановки…")
        for _ in range(6):  # до ~3 секунд ждём, пока winws действительно исчезнет
            if not self._tasklist("winws.exe", 0.0):
                break
            time.sleep(0.5)
        if self.state():
            self._emit("! winws всё ещё работает")
            self._emit("! возможно, он запущен вне программы или работает как служба")
            self._emit('! вручную: taskkill /F /IM winws.exe  (или перезагрузите ПК)')
        else:
            self._emit("> остановлен")
        return not self.state()

    # ------------------------------------------------------------- самопроверка / сервис

    def check_sites(self, log=None) -> bool:
        """Проверяет доступность YouTube и Discord (простой HTTPS-запрос)."""
        self._log = log
        import time as _t
        tests = [("YouTube", "https://www.youtube.com"),
                 ("Discord", "https://discord.com")]
        all_ok = True
        for name, url in tests:
            t0 = _t.time()
            try:
                req = urllib.request.Request(
                    url, headers={"User-Agent":
                                  "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
                with urllib.request.urlopen(req, timeout=8) as resp:
                    code = resp.status
                dt = _t.time() - t0
                self._emit(f"✓ {name}: ответ {code} за {dt:.1f} с")
            except Exception as exc:
                dt = _t.time() - t0
                all_ok = False
                reason = getattr(exc, "reason", None) or exc
                self._emit(f"✗ {name}: {reason} ({dt:.1f} с)")
        self._emit("✓ сайты отвечают" if all_ok
                   else "! не всё отвечает — попробуйте другой способ обхода")
        return all_ok

    def clear_discord_cache(self, log=None) -> bool:
        """Очищает кэш Discord текущего пользователя (как clear_discord_cache)."""
        self._log = log
        subs = ("Cache", "Code Cache", "GPUCache", "DawnGraphiteCache",
                "blob_storage")
        cleared = 0
        roots = []
        for var in ("APPDATA", "LOCALAPPDATA"):
            base = os.environ.get(var)
            if base:
                roots.append(Path(base) / "discord")
        found_any = False
        for root in roots:
            if not root.is_dir():
                continue
            found_any = True
            self._emit(f"> кэш Discord: {root}")
            for sub in subs:
                d = root / sub
                if not d.is_dir():
                    continue
                for child in d.iterdir():
                    try:
                        if child.is_dir():
                            import shutil as _sh
                            _sh.rmtree(child, ignore_errors=True)
                        else:
                            child.unlink(missing_ok=True)
                        cleared += 1
                    except Exception:
                        pass
        if not found_any:
            self._emit("! папка Discord не найдена (кэша нет)")
            return False
        self._emit(f"> очищено элементов кэша: {cleared}")
        self._emit("> закройте и откройте Discord, если он запущен")
        return True

    # ------------------------------------------------------------- Telegram (Tg WS Proxy)

    def _tg_exe(self) -> Path:
        return self.root / "tgws" / "TgWsProxy.exe"

    @staticmethod
    def _tg_latest_tag():
        try:
            data = _http_json("https://api.github.com/repos/Flowseal/tg-ws-proxy/releases/latest")
            return data.get("tag_name", "") or ""
        except Exception:
            return ""

    def telegram_installed(self) -> str:
        m = self.root / ".tgws-version"
        return m.read_text(encoding="utf-8").strip() if m.exists() else ""

    def telegram_latest(self) -> str:
        return self._tg_latest_tag()

    def download_telegram(self, log=None) -> bool:
        self._log = log
        tag = self._tg_latest_tag()
        if not tag:
            if log:
                log("! не удалось определить версию Tg WS Proxy")
            return False
        url = (f"https://github.com/Flowseal/tg-ws-proxy/releases/download/"
               f"{tag}/TgWsProxy_windows.exe")
        try:
            self._emit(f"> скачивание Tg WS Proxy {tag}…")
            (self.root / "tgws").mkdir(exist_ok=True)
            req = urllib.request.Request(url, headers=_AUTH_HEADERS)
            with urllib.request.urlopen(req, timeout=300) as resp:
                self._tg_exe().write_bytes(resp.read())
            (self.root / ".tgws-version").write_text(tag, encoding="utf-8")
            self._emit(f"> Tg WS Proxy {tag} установлен")
            return True
        except Exception as exc:
            if log:
                log(f"! ошибка скачивания: {exc}")
            return False

    def telegram_running(self) -> bool:
        return self._tasklist("TgWsProxy.exe")

    def telegram_start(self, log=None) -> bool:
        self._log = log
        exe = self._tg_exe()
        if not exe.exists():
            self._emit("! Tg WS Proxy не скачан — вкладка «Обновление»/Telegram")
            return False
        if self.telegram_running():
            self._emit("! Tg WS Proxy уже запущен")
            return False
        try:
            subprocess.Popen([str(exe)])
            self._task_cache.pop("TgWsProxy.exe", None)
            self._emit("> запущен Tg WS Proxy (окно настроек)…")
            return True
        except Exception as exc:
            self._emit(f"! ошибка запуска: {exc}")
            return False

    def telegram_stop(self, log=None) -> bool:
        self._log = log
        if os.name == "nt":
            subprocess.run(["taskkill", "/F", "/IM", "TgWsProxy.exe"],
                           capture_output=True, text=True, timeout=15,
                           creationflags=CREATE_NO_WINDOW)
        self._task_cache.pop("TgWsProxy.exe", None)
        self._emit("> Tg WS Proxy остановлен")
        return True

    def telegram_config(self) -> dict:
        base = os.environ.get("APPDATA")
        if not base:
            return {}
        cfg = Path(base) / "TgWsProxy" / "config.json"
        return read_json(cfg)

    def telegram_connect_link(self) -> str:
        """tg://proxy-ссылка из конфига (host/port/secret)."""
        cfg = self.telegram_config()
        host = cfg.get("host", "127.0.0.1")
        port = cfg.get("port", 1443)
        secret = cfg.get("secret", "")
        if not secret:
            return ""
        return f"tg://proxy?server={host}&port={port}&secret={secret}"

    # ------------------------------------------------------------- автозапуск

    @staticmethod
    def _launch_cmd():
        if getattr(sys, "frozen", False):
            return f'"{sys.executable}"'
        return f'"{sys.executable}" -m gui.app.main'

    def autostart_state(self) -> str:
        if os.name != "nt":
            return ""
        try:
            p = subprocess.run(["schtasks", "/Query", "/TN", "Zapret-GUI"],
                               capture_output=True, text=True, timeout=20,
                               creationflags=CREATE_NO_WINDOW)
            return "on" if p.returncode == 0 else "off"
        except Exception:
            return "off"

    def autostart(self, enable: bool, log=None) -> bool:
        self._log = log
        if os.name != "nt":
            if log:
                log("! автозапуск доступен только на Windows")
            return False
        name = "Zapret-GUI"
        if enable:
            cmd = ["schtasks", "/Create", "/F", "/TN", name,
                   "/TR", self._launch_cmd(), "/SC", "ONLOGON",
                   "/RL", "HIGHEST", "/IT"]
            if log:
                log(f"> создаю задачу планировщика «{name}» (при входе)")
        else:
            cmd = ["schtasks", "/Delete", "/F", "/TN", name]
            if log:
                log(f"> удаляю задачу «{name}»")
        try:
            p = subprocess.run(cmd, capture_output=True, text=True, timeout=30,
                               creationflags=CREATE_NO_WINDOW)
            out = (p.stdout or "") + (p.stderr or "")
            for line in out.splitlines():
                self._emit(line)
            if p.returncode != 0 and log:
                log("! schtasks вернул ошибку — нужны права администратора")
            return p.returncode == 0
        except Exception as exc:
            if log:
                log(f"! ошибка: {exc}")
            return False

# =============================================================================
# Windows-бэкенд: winws.exe + WinDivert, стратегии Flowseal, планировщик задач
# =============================================================================

import io
import json
import os
import re
import shlex
import subprocess
import sys
import time
import urllib.request
import zipfile
from pathlib import Path

from .backend import (
    APP_VERSION, Backend, GITHUB_REPO, GITHUB_URL, STRATEGIES_REPO, CORE_REPO,
    app_root, read_json, strategy_description_from_bat, write_json,
)

CREATE_NO_WINDOW = 0x08000000

_AUTH_HEADERS = {"User-Agent": f"zapret-gui/{APP_VERSION}"}
CONFIG_NAME = "config.json"
STRAT_MARK = ".strategies-rev"
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


def _download(url, dest: Path):
    req = urllib.request.Request(url, headers=_AUTH_HEADERS)
    with urllib.request.urlopen(req, timeout=120) as resp:
        dest.write_bytes(resp.read())


def _short(rev):
    return rev if not rev else rev[:10]


class WinBackend(Backend):
    name = "windows"

    def __init__(self):
        self.root = app_root()
        self.strategies_dir = self.root / "strategies"
        self.bin_dir = self.root / "bin"
        self.config_file = self.root / CONFIG_NAME
        self.logs_dir = self.root / "logs"
        self._proc_infos = []      # [{proc, log}]
        self._log = lambda _line: None

    # ------------------------------------------------------------- пути

    def _winws(self) -> Path:
        return self.bin_dir / "winws.exe"

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
        names = []
        if self.strategies_dir.is_dir():
            names = sorted(f.name for f in self.strategies_dir.glob("*.bat"))
        # general.bat первым
        names.sort(key=lambda n: (n.lower() != "general.bat", n.lower()))
        return names

    def strategy_description(self, name: str) -> str:
        p = self.strategies_dir / name
        return strategy_description_from_bat(p, name) if p.exists() else ""

    # ------------------------------------------------------------- загрузка Flowseal

    def _flowseal_zip(self) -> Path:
        return self.root / ".flowseal.zip"

    def _fetch_flowseal(self, log) -> bool:
        """Качает и распаковывает Flowseal main в strategies/.win-src."""
        url = f"https://codeload.github.com/{STRATEGIES_REPO}/zip/refs/heads/main"
        try:
            self._emit("> скачивание Flowseal (стратегии + winws + WinDivert)…")
            _download(url, self._flowseal_zip())
        except Exception as exc:
            if log:
                log(f"! ошибка скачивания: {exc}")
            return False
        src = self.root / ".flowseal-src"
        if src.exists():
            import shutil
            shutil.rmtree(src, ignore_errors=True)
        src.mkdir()
        try:
            with zipfile.ZipFile(self._flowseal_zip()) as z:
                z.extractall(src)
        except Exception as exc:
            if log:
                log(f"! ошибка распаковки: {exc}")
            return False
        # единственная верхняя папка репо
        for child in src.iterdir():
            if child.is_dir():
                return child
        return None

    def _rev_from_flowseal(self):
        try:
            info = _http_json(f"https://api.github.com/repos/{STRATEGIES_REPO}/commits/main?per_page=1")
            return info.get("sha", "")
        except Exception:
            return ""

    def _apply_strategies(self, repo: Path, log):
        dest = self.strategies_dir
        dest.mkdir(exist_ok=True)
        for p in repo.glob("*.bat"):
            (dest / p.name).write_bytes(p.read_bytes())
        lists_dir = dest / "lists"
        lists_dir.mkdir(exist_ok=True)
        for p in (repo / "lists").glob("*.txt"):
            (lists_dir / p.name).write_bytes(p.read_bytes())
        bin_dir = dest / "bin"
        bin_dir.mkdir(exist_ok=True)
        for p in (repo / "bin").glob("*.bin"):
            (bin_dir / p.name).write_bytes(p.read_bytes())
        rev = self._rev_from_flowseal()
        if rev:
            (self.root / STRAT_MARK).write_text(rev, encoding="utf-8")
        return True

    def strategies_installed(self) -> str:
        m = self.root / STRAT_MARK
        if m.exists():
            return m.read_text(encoding="utf-8").strip()
        return ""

    def strategies_latest(self) -> str:
        return self._rev_from_flowseal()

    def download_strategies(self, log=None) -> bool:
        self._log = log
        repo = self._fetch_flowseal(log)
        if not repo:
            return False
        ok = self._apply_strategies(repo, log)
        self._emit("> стратегии обновлены")
        return ok

    # ------------------------------------------------------------- ядро winws

    def _apply_core(self, repo: Path, log):
        self.bin_dir.mkdir(exist_ok=True)
        bins = {"winws.exe", "WinDivert64.sys", "WinDivert.dll", "cygwin1.dll"}
        copied = []
        for p in repo.rglob("*"):
            if p.is_file() and p.name in bins:
                target = self.bin_dir / p.name
                target.write_bytes(p.read_bytes())
                copied.append(p.name)
        if "winws.exe" not in copied:
            if log:
                log("! winws.exe не найден в пакете Flowseal")
            return False
        return True

    def core_installed(self) -> str:
        w = self._winws()
        if not w.exists():
            return ""
        try:
            p = subprocess.run([str(w), "--version"], capture_output=True,
                               text=True, timeout=15, errors="replace")
            out = (p.stdout or "") + (p.stderr or "")
            for line in out.splitlines():
                if "version" in line.lower():
                    return line.strip()
        except Exception:
            pass
        return ""

    def core_latest(self) -> str:
        # Ядро ставим из пакета Flowseal — точную версию отдельно не выводим.
        return ""

    def download_core(self, log=None) -> bool:
        self._log = log
        repo = self._fetch_flowseal(log)
        if not repo:
            return False
        ok = self._apply_core(repo, log)
        if ok:
            self._emit("> ядро (winws + WinDivert) готово")
        return ok

    # ------------------------------------------------------------- программа

    def program_latest(self):
        try:
            data = _http_json(f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest")
            tag = data.get("tag_name", "") or ""
            notes = data.get("body", "") or ""
            return tag, notes
        except Exception:
            return "", ""

    def update_program(self, log=None) -> bool:
        # Первая версия: открываем страницу релизов — пользователь скачивает exe.
        if log:
            log("> самообновление появится в следующей версии.")
            log(f"> открываю страницу релизов: {GITHUB_URL}/releases/latest")
        try:
            import webbrowser
            webbrowser.open(f"{GITHUB_URL}/releases/latest")
        except Exception:
            pass
        return False

    # ------------------------------------------------------------- запуск winws

    @staticmethod
    def _bat_commands(path: Path):
        """Разбирает .bat Flowseal: возвращает списки аргументов winws."""
        raw = path.read_text(encoding="utf-8", errors="replace").replace("\r", "")
        # склейка строк с переносом '^'
        logical = []
        cur = ""
        for line in raw.splitlines():
            s = line.rstrip()
            if s.endswith("^"):
                cur += s[:-1] + " "
            else:
                cur += s
                logical.append(cur)
                cur = ""
        if cur.strip():
            logical.append(cur)

        cmds = []
        for stmt in logical:
            stmt = stmt.strip()
            m = re.search(r"\bwinws\b(.*)", stmt)
            if not m:
                continue
            rest = m.group(1)
            # обрезаем хвост вроде "if errorlevel", "goto", "&&"
            cut = len(rest)
            low = rest.lower()
            for kw in ("if errorlevel", "&&", "goto ", "if %errorlevel%"):
                i = low.find(kw)
                if i != -1:
                    cut = min(cut, i)
            rest = rest[:cut].strip()
            if not rest:
                continue
            try:
                args = shlex.split(rest, posix=False)
            except ValueError:
                args = rest.split()
            cmds.append(args)
        return cmds

    def state(self) -> bool:
        # оставшиеся после нас процессы
        if any(i["proc"].poll() is None for i in self._proc_infos):
            return True
        # и любые winws в системе (например, запущенный ранее)
        if os.name == "nt":
            try:
                p = subprocess.run(
                    ["tasklist", "/FI", "IMAGENAME eq winws.exe"],
                    capture_output=True, text=True, timeout=15,
                    creationflags=CREATE_NO_WINDOW,
                )
                return "winws.exe" in (p.stdout or "")
            except Exception:
                return False
        return False

    def explain(self, log=None):
        """Выводит в лог причины остановки завершившихся winws-процессов.

        Вызывается из «Статуса» периодически и после запуска: если процесс
        упал сам (не был остановлен пользователем) — показывает код выхода и
        хвост его лог-файла. Возвращает True, если что-то выведено.
        """
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

    def start(self, strategy: str, log=None) -> bool:
        self._log = log
        if self.state():
            self._emit("! обход уже запущен")
            return False
        w = self._winws()
        if not w.exists():
            self._emit("! winws.exe не найден — скачайте ядро (вкладка «Обновление»)")
            return False
        bat = self.strategies_dir / strategy
        if not bat.exists():
            self._emit(f"! стратегия не найдена: {strategy}")
            return False
        try:
            cmds = self._bat_commands(bat)
        except Exception as exc:
            self._emit(f"! не удалось разобрать .bat: {exc}")
            return False
        if not cmds:
            self._emit("! в стратегии не найдено команд winws")
            return False

        self.logs_dir.mkdir(exist_ok=True)
        stamp = time.strftime("%Y%m%d-%H%M%S")
        self._proc_infos = []
        self._emit(f"> запуск обхода ({strategy}), процессов: {len(cmds)}")
        for idx, args in enumerate(cmds, 1):
            logpath = self.logs_dir / f"winws-{idx}-{stamp}.log"
            try:
                fh = open(logpath, "a", encoding="utf-8", errors="replace")
            except Exception as exc:
                self._emit(f"! не открыть лог {logpath}: {exc}")
                continue
            try:
                proc = subprocess.Popen(
                    [str(w), *args],
                    cwd=str(self.strategies_dir),
                    stdout=fh, stderr=subprocess.STDOUT,
                    creationflags=CREATE_NO_WINDOW,
                )
            except Exception as exc:
                fh.close()
                self._emit(f"! ошибка запуска winws: {exc}")
                continue
            self._proc_infos.append({"proc": proc, "log": logpath, "acked": False})
            self._emit(f"> winws {idx} запущен (pid {proc.pid}) — лог: {logpath.name}")
        return self.state()

    def stop(self, log=None) -> bool:
        self._log = log
        self._emit("> остановка обхода")
        for info in self._proc_infos:
            info["acked"] = True   # штатная остановка — причину не показываем
            proc = info["proc"]
            if proc.poll() is None:
                try:
                    proc.terminate()
                except Exception:
                    pass
        self._proc_infos = []
        if os.name == "nt":
            subprocess.run(["taskkill", "/F", "/IM", "winws.exe"],
                           capture_output=True, text=True, timeout=15,
                           creationflags=CREATE_NO_WINDOW)
        self._emit("> остановлен")
        return True

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

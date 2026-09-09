# =============================================================================
# Вкладка «Обновление» — программа, ядро winws, стратегии Flowseal
# =============================================================================

from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QPlainTextEdit, QVBoxLayout, QWidget,
)

from ..backend import APP_VERSION
from ..jobs import JobThread
from .widgets import add_row, log_line, make_button, make_card, make_title


def _short(rev):
    return rev[:10] + "…" if rev and len(rev) > 10 else (rev or "—")


class UpdateTab(QWidget):
    def __init__(self, backend, parent=None):
        super().__init__(parent)
        self.b = backend
        self._jobs = []
        self._latest = {}          # module -> (installed, available)
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(10)
        root.addWidget(make_title("Обновление", "Версии и обновление компонентов"))

        # Программа
        prog = make_card()
        pl = prog.layout()
        ph = QLabel(">_ программа (GUI)")
        ph.setObjectName("logHeader")
        pl.addWidget(ph)
        self.prog_val = QLabel(APP_VERSION)
        self.prog_val.setObjectName("valueLabel")
        pl.addWidget(add_row("Версия", self.prog_val))
        self.prog_btn = make_button("⬇ Обновить программу")
        self.prog_btn.setMinimumWidth(200)
        pl.addWidget(self._right(self.prog_btn))
        self.prog_btn.clicked.connect(lambda: self._run("program", self.prog_btn))
        root.addWidget(prog)

        # Ядро
        core = make_card()
        cl = core.layout()
        ch = QLabel(">_ ядро (winws + WinDivert)")
        ch.setObjectName("logHeader")
        cl.addWidget(ch)
        self.core_val = QLabel("—")
        self.core_val.setObjectName("valueLabel")
        cl.addWidget(add_row("Установлено", self.core_val))
        self.core_btn = make_button("⬇ Скачать/обновить ядро")
        self.core_btn.setMinimumWidth(200)
        cl.addWidget(self._right(self.core_btn))
        self.core_btn.clicked.connect(lambda: self._run("core", self.core_btn))
        root.addWidget(core)

        # Стратегии
        strat = make_card()
        sl = strat.layout()
        sh = QLabel(">_ стратегии (Flowseal)")
        sh.setObjectName("logHeader")
        sl.addWidget(sh)
        self.strat_val = QLabel("—")
        self.strat_val.setObjectName("valueLabel")
        sl.addWidget(add_row("Ревизия", self.strat_val))
        self.strat_btn = make_button("⬇ Скачать/обновить стратегии")
        self.strat_btn.setMinimumWidth(200)
        sl.addWidget(self._right(self.strat_btn))
        self.strat_btn.clicked.connect(lambda: self._run("strat", self.strat_btn))
        root.addWidget(strat)

        # Лог
        log_card = make_card()
        ll = log_card.layout()
        lh = QLabel(">_ вывод")
        lh.setObjectName("logHeader")
        ll.addWidget(lh)
        self.log_view = QPlainTextEdit()
        self.log_view.setObjectName("logView")
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumBlockCount(1000)
        ll.addWidget(self.log_view, 1)
        root.addWidget(log_card, 1)

    @staticmethod
    def _right(button):
        row = QWidget()
        lay = QHBoxLayout(row)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addStretch()
        lay.addWidget(button)
        return row

    def _run(self, which, btn):
        if any(j.isRunning() for j in self._jobs):
            self.append_log("! операция уже выполняется")
            return
        funcs = {
            "program": lambda log: self.b.update_program(log=log),
            "core": lambda log: self.b.download_core(log=log),
            "strat": lambda log: self.b.download_strategies(log=log),
        }
        self.append_log(f"> {which}: запуск…")
        btn.setEnabled(False)
        job = JobThread(funcs[which])
        job.line.connect(self.append_log)
        job.finished.connect(lambda: (btn.setEnabled(True), self._refresh()))
        self._jobs.append(job)
        job.finished.connect(lambda: self._jobs.remove(job) if job in self._jobs else None)
        job.start()

    def on_show(self):
        self._refresh()

    def _refresh(self):
        # Показываем установленные значения (быстро, без сети).
        self.core_val.setText(self.b.core_installed() or "не установлено")
        self.strat_val.setText(_short(self.b.strategies_installed()))
        self.prog_val.setText(APP_VERSION)

    def append_log(self, text):
        log_line(self.log_view, text)
        sb = self.log_view.verticalScrollBar()
        sb.setValue(sb.maximum())

# =============================================================================
# Вкладка «Статус» — запуск/остановка обхода и журнал
# =============================================================================

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QPlainTextEdit, QPushButton, QVBoxLayout, QWidget,
)

from ..jobs import JobThread
from .widgets import log_line, make_button, make_card, make_title

_RUN = "#66bb6a"
_STOP = "#616161"


class StatusTab(QWidget):
    def __init__(self, backend, parent=None):
        super().__init__(parent)
        self.b = backend
        self._job = None
        self._was_running = None
        self._build_ui()

        self._timer = QTimer(self)
        self._timer.timeout.connect(self.refresh)
        self._timer.start(3000)
        self.refresh()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)
        root.addWidget(make_title("Статус", "Состояние обхода и управление запуском"))

        card = make_card()
        cl = card.layout()
        self.state_label = QLabel()
        self.state_label.setObjectName("statusLabel")
        cl.addWidget(self.state_label)

        btn_row = QWidget()
        bl = QHBoxLayout(btn_row)
        bl.setContentsMargins(0, 0, 0, 0)
        bl.setSpacing(10)
        self.start_btn = make_button("▶ Включить обход", primary=True)
        self.stop_btn = make_button("⏹ Выключить", danger=True)
        self.start_btn.setMinimumWidth(150)
        self.stop_btn.setMinimumWidth(150)
        bl.addWidget(self.start_btn)
        bl.addWidget(self.stop_btn)
        bl.addStretch()
        cl.addWidget(btn_row)
        root.addWidget(card)

        log_card = make_card()
        ll = log_card.layout()
        header = QLabel(">_ журнал")
        header.setObjectName("logHeader")
        ll.addWidget(header)
        self.log_view = QPlainTextEdit()
        self.log_view.setObjectName("logView")
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumBlockCount(3000)
        ll.addWidget(self.log_view, 1)
        root.addWidget(log_card, 1)

        self.start_btn.clicked.connect(self._start)
        self.stop_btn.clicked.connect(self._stop)

    def _guard(self):
        if self._job and self._job.isRunning():
            self.append_log("! операция уже выполняется")
            return True
        return False

    def _start(self):
        if self._guard():
            return
        strategy = self.b.read_config().get("strategy", "")
        if not strategy:
            self.append_log("! способ обхода не выбран — вкладка «Способ обхода»")
            return
        self._busy(True)
        self._job = JobThread(lambda log: self.b.start(strategy, log=log))
        self._wire(self._job, self._start)
        self._job.start()

    def _stop(self):
        if self._guard():
            return
        self._busy(True)
        self._job = JobThread(lambda log: self.b.stop(log=log))
        self._wire(self._job, self._stop)
        self._job.start()

    def _wire(self, job, btn):
        job.line.connect(self.append_log)
        job.finished.connect(lambda: self._done(btn))

    def _busy(self, busy):
        self.start_btn.setEnabled(not busy)
        self.stop_btn.setEnabled(not busy)

    def _done(self, btn):
        self._job = None
        self._busy(False)
        self.refresh()
        # Проверяем через 1.5 с: не упал ли winws сразу после запуска
        QTimer.singleShot(1500, self._maybe_explain)

    def _maybe_explain(self):
        try:
            self.b.explain(self.append_log)
        except Exception:
            pass
        self.refresh()

    def on_show(self):
        self.refresh()

    def refresh(self):
        running = self.b.state()
        # Переход «работал → упал»: выводим причину (код выхода + лог)
        if self._was_running is True and not running:
            self._maybe_explain()
        self._was_running = running
        if running:
            self.state_label.setText("[СТАТУС: РАБОТАЕТ]")
            self.state_label.setStyleSheet(f"color: {_RUN};")
            self.start_btn.setEnabled(False)
            self.stop_btn.setEnabled(True)
        else:
            self.state_label.setText("[СТАТУС: ОСТАНОВЛЕН]")
            self.state_label.setStyleSheet(f"color: {_STOP};")
            self.start_btn.setEnabled(True)
            self.stop_btn.setEnabled(False)

    def append_log(self, text):
        log_line(self.log_view, text)
        sb = self.log_view.verticalScrollBar()
        sb.setValue(sb.maximum())

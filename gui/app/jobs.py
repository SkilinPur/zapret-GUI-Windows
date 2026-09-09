# =============================================================================
# JobThread — выполнение долгой операции бэкенда в фоне с потоком лога
# =============================================================================

from PySide6.QtCore import QThread, Signal


class JobThread(QThread):
    line = Signal(str)
    done = Signal(object)   # (ok: bool, error: str)

    def __init__(self, func, parent=None):
        super().__init__(parent)
        self._func = func
        self._ok = False
        self._err = ""

    def run(self):
        try:
            self._ok = bool(self._func(self._emit))
        except Exception as exc:
            self._err = str(exc)
            self._ok = False

    def _emit(self, text):
        self.line.emit(text)

    def result(self):
        return self._ok, self._err

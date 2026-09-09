# =============================================================================
# Точка входа GUI (Windows-версия). Запуск: python -m gui.app.main
# =============================================================================

import os
import sys

from PySide6.QtWidgets import QApplication

from .theme import QSS
from .window import MainWindow


def make_backend():
    if os.name == "nt":
        from .win_backend import WinBackend
        return WinBackend()
    from .mock_backend import MockBackend
    return MockBackend()


def main():
    os.environ.setdefault("QT_AUTO_SCREEN_SCALE_FACTOR", "1")

    app = QApplication(sys.argv)
    app.setApplicationName("Zapret Discord YouTube")
    app.setOrganizationName("InIProject")
    app.setStyleSheet(QSS)

    win = MainWindow(make_backend())
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

# =============================================================================
# Главное окно — шапка, боковая панель, контент (Windows)
# =============================================================================

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QListWidget, QMainWindow, QStackedWidget,
    QVBoxLayout, QWidget,
)

from .tray import install_tray, make_icon
from .ui.config_tab import ConfigTab
from .ui.help_tab import HelpTab
from .ui.status_tab import StatusTab
from .ui.update_tab import UpdateTab

NAV_ITEMS = [
    ("🟢 Статус", StatusTab),
    ("⚙️ Способ обхода", ConfigTab),
    ("⬆️ Обновление", UpdateTab),
    ("📖 Как пользоваться", HelpTab),
]

SIDEBAR_WIDTH = 200


class MainWindow(QMainWindow):
    def __init__(self, backend):
        super().__init__()
        self.backend = backend
        self._tabs = []
        self._really_quit = False
        self._build_ui()
        self.setWindowTitle("Zapret Discord YouTube — Windows")
        self.resize(920, 620)
        self.setWindowIcon(make_icon())
        try:
            self._tray = install_tray(self)
        except Exception:
            self._tray = None

    def _build_ui(self):
        central = QWidget()
        central.setObjectName("rootWidget")
        self.setCentralWidget(central)

        outer = QVBoxLayout(central)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(self._build_header())

        body = QWidget()
        bl = QHBoxLayout(body)
        bl.setContentsMargins(0, 0, 0, 0)
        bl.setSpacing(0)
        bl.addWidget(self._build_sidebar())
        bl.addWidget(self._build_content(), 1)
        outer.addWidget(body, 1)

    def _build_header(self):
        header = QWidget()
        header.setObjectName("headerBar")
        layout = QHBoxLayout(header)
        layout.setContentsMargins(18, 10, 18, 10)
        layout.setSpacing(12)

        brand = QLabel("InIProject")
        brand.setObjectName("brandLabel")
        sub = QLabel("Zapret Discord YouTube — обход замедления")
        sub.setObjectName("subtitleLabel")
        layout.addWidget(brand)
        layout.addSpacing(8)
        layout.addWidget(sub)
        layout.addStretch()
        return header

    def _build_sidebar(self):
        side = QWidget()
        side.setObjectName("sidebarWidget")
        side.setFixedWidth(SIDEBAR_WIDTH)
        layout = QVBoxLayout(side)
        layout.setContentsMargins(8, 12, 8, 12)
        layout.setSpacing(8)

        self.nav = QListWidget()
        self.nav.setObjectName("sidebarList")
        for name, _ in NAV_ITEMS:
            self.nav.addItem(name)
        layout.addWidget(self.nav, 1)

        footer = QLabel("InIProject")
        footer.setObjectName("sidebarFooter")
        footer.setAlignment(Qt.AlignCenter)
        layout.addWidget(footer)

        self.nav.currentRowChanged.connect(self._change_tab)
        self.nav.setCurrentRow(0)
        return side

    def _build_content(self):
        self.stack = QStackedWidget()
        for _name, tab_cls in NAV_ITEMS:
            tab = tab_cls(self.backend)
            self._tabs.append(tab)
            self.stack.addWidget(tab)
        return self.stack

    def _change_tab(self, row):
        if 0 <= row < len(self._tabs):
            self.stack.setCurrentIndex(row)
            refresh = getattr(self._tabs[row], "on_show", None)
            if refresh is not None:
                refresh()

    def show_from_tray(self):
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def quit_from_tray(self):
        self._really_quit = True
        self.close()

    def closeEvent(self, event):
        if self._tray is not None and not self._really_quit:
            event.ignore()
            self.hide()
            return
        event.accept()

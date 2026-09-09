# =============================================================================
# Вкладка «Как пользоваться» (Windows) — краткая справка
# =============================================================================

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from .widgets import make_card, make_title


class HelpTab(QWidget):
    def __init__(self, backend, parent=None):
        super().__init__(parent)
        self.b = backend
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)
        root.addWidget(make_title("Как пользоваться", "Несколько шагов до работающего обхода"))

        quick = make_card()
        ql = quick.layout()
        ql.addWidget(QLabel(
            "1. Вкладка «Обновление» — скачать ядро и стратегии (первый раз).\n"
            "2. Вкладка «Способ обхода» — выбрать способ (general.bat — базовый).\n"
            "3. Вкладка «Статус» — «Включить обход».\n"
            "4. Проверить YouTube/Discord. Не помогло — попробовать другой способ.\n\n"
            "Программа должна быть запущена от имени администратора."
        ))
        root.addWidget(quick)
        root.addStretch()

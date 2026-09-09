# =============================================================================
# Вкладка «Способ обхода» — выбор стратегии с описанием
# =============================================================================

from PySide6.QtWidgets import (
    QComboBox, QHBoxLayout, QLabel, QVBoxLayout, QWidget,
)

from .widgets import add_row, make_button, make_card, make_title

GF_LABELS = {"off": "Выкл", "all": "TCP и UDP", "tcp": "TCP", "udp": "UDP"}
IPSET_LABELS = {"any": "Весь трафик", "none": "Только списки", "loaded": "По списку IP"}


class ConfigTab(QWidget):
    def __init__(self, backend, parent=None):
        super().__init__(parent)
        self.b = backend
        self._build_ui()
        self.reload()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)
        root.addWidget(make_title("Способ обхода", "Как именно обманывать замедление"))

        card = make_card()
        cl = card.layout()

        self.combo = QComboBox()
        self.combo.setMinimumHeight(34)
        cl.addWidget(add_row("Способ обхода", self.combo))

        self.desc = QLabel("—")
        self.desc.setObjectName("statusMetaLabel")
        self.desc.setWordWrap(True)
        cl.addWidget(self.desc)

        self.combo.currentIndexChanged.connect(self._show_desc)

        btn_row = QWidget()
        bl = QHBoxLayout(btn_row)
        bl.setContentsMargins(0, 0, 0, 0)
        self.save_btn = make_button("💾 Применить способ", primary=True)
        self.save_btn.setMinimumWidth(220)
        bl.addWidget(self.save_btn)
        bl.addStretch()
        cl.addWidget(btn_row)
        self.save_btn.clicked.connect(self._save)
        root.addWidget(card)

        hint = QLabel(
            "Если после включения YouTube/Discord не ускорились — вернитесь сюда "
            "и выберите другой способ, либо напишите в поддержку с описанием проблемы."
        )
        hint.setObjectName("statusMetaLabel")
        hint.setWordWrap(True)
        root.addWidget(hint)

        # --- Дополнительные фильтры (как у Flowseal) --------------------
        extra = make_card()
        el = extra.layout()
        ehead = QLabel("Дополнительные фильтры")
        ehead.setObjectName("logHeader")
        el.addWidget(ehead)

        self.gf_combo = QComboBox()
        for key, label in GF_LABELS.items():
            self.gf_combo.addItem(label, key)
        el.addWidget(add_row("GameFilter", self.gf_combo))
        gf_hint = QLabel(
            "Игровые порты 1024–65535 для TCP/UDP. Обычно выкл — включайте, "
            "если игры/голос не работают при активном обходе."
        )
        gf_hint.setObjectName("statusMetaLabel")
        gf_hint.setWordWrap(True)
        el.addWidget(gf_hint)

        self.ipset_combo = QComboBox()
        for key, label in IPSET_LABELS.items():
            self.ipset_combo.addItem(label, key)
        el.addWidget(add_row("Охват (ipset)", self.ipset_combo))
        ip_hint = QLabel(
            "К каким адресам применять обход: весь трафик / только списки / "
            "по полному списку IP."
        )
        ip_hint.setObjectName("statusMetaLabel")
        ip_hint.setWordWrap(True)
        el.addWidget(ip_hint)
        root.addWidget(extra)

        self.gf_combo.currentIndexChanged.connect(self._save_filters)
        self.ipset_combo.currentIndexChanged.connect(self._save_filters)

        self._load_filters()
        root.addStretch()

    def reload(self):
        cfg = self.b.read_config()
        names = self.b.strategies()
        current = cfg.get("strategy") or ("general.bat" if "general.bat" in names else (names[0] if names else ""))
        self.combo.blockSignals(True)
        self.combo.clear()
        self.combo.addItems(names)
        idx = self.combo.findText(current)
        self.combo.setCurrentIndex(idx if idx >= 0 else 0)
        self.combo.blockSignals(False)
        self._show_desc()

    def _show_desc(self):
        name = self.combo.currentText()
        self.desc.setText(self.b.strategy_description(name) or "Описание не найдено")

    def _save(self):
        name = self.combo.currentText()
        if name and self.b.save_strategy(name):
            self.desc.setText(self.desc.text())
        else:
            self.desc.setText(f"! не удалось сохранить «{name}»")

    def on_show(self):
        self.reload()
        self._load_filters()

    def _index_of(self, combo, key):
        for i in range(combo.count()):
            if combo.itemData(i) == key:
                return i
        return -1

    def _load_filters(self):
        self.gf_combo.blockSignals(True)
        i = self._index_of(self.gf_combo, self.b.game_filter_state())
        self.gf_combo.setCurrentIndex(i if i >= 0 else 0)
        self.gf_combo.blockSignals(False)
        self.ipset_combo.blockSignals(True)
        i = self._index_of(self.ipset_combo, self.b.ipset_state())
        self.ipset_combo.setCurrentIndex(i if i >= 0 else 0)
        self.ipset_combo.blockSignals(False)

    def _save_filters(self):
        gf = self.gf_combo.currentData()
        ip = self.ipset_combo.currentData()
        self.b.set_game_filter(gf)
        self.b.set_ipset(ip)

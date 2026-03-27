from PyQt5.QtWidgets import QPushButton, QLabel, QHBoxLayout
from PyQt5.QtGui import QIcon
from PyQt5.QtCore import pyqtSignal, Qt

PIPELINE_MODE = "pipeline"
REACT_MODE = "react"


class AgentModeButton(QPushButton):
    """
    Toggle button that switches between Pipeline and ReAct agent modes.
    Styled to match WebSearchButton.
    Emits mode_changed(str) with value 'pipeline' or 'react'.
    """
    mode_changed = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._mode = PIPELINE_MODE
        self._init_ui()
        self.clicked.connect(self._toggle)

    def _init_ui(self):
        self.setObjectName('agent_mode_button')
        self.setStyleSheet('''
            QPushButton {
                width: 110px;
                height: 36px;
                background: #2b2b2b;
                border: 1px solid #3c3c3c;
                border-radius: 8px;
            }
            QPushButton:hover {
                background-color: #3c3c3c;
            }
            QPushButton:pressed {
                background-color: #1e1e1e;
            }
        ''')

        self.icon_label = QLabel()
        self.icon_label.setFixedSize(24, 16)
        self.icon_label.setPixmap(QIcon("ui/icon/code.png").pixmap(24, 16))
        self.icon_label.setStyleSheet("""
            QLabel {
                border: none;
                background: transparent;
            }
        """)

        self.name_label = QLabel("Pipeline")
        self.name_label.setStyleSheet("""
            QLabel {
                font-family: 'Source Han Sans SC';
                font-weight: 400;
                font-size: 14px;
                color: #FFFFFF;
                line-height: 18px;
                border: none;
                background: transparent;
            }
        """)

        layout = QHBoxLayout()
        layout.setSpacing(3)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.addWidget(self.icon_label, 0, Qt.AlignVCenter)
        layout.addWidget(self.name_label, 0, Qt.AlignVCenter)
        self.setLayout(layout)

    def _toggle(self):
        if self._mode == PIPELINE_MODE:
            self._mode = REACT_MODE
            self.name_label.setText("ReAct")
        else:
            self._mode = PIPELINE_MODE
            self.name_label.setText("Pipeline")

        # Force style refresh
        self.name_label.style().unpolish(self.name_label)
        self.name_label.style().polish(self.name_label)

        self.mode_changed.emit(self._mode)

    def current_mode(self) -> str:
        return self._mode

    def reset(self):
        """Reset to Pipeline mode (e.g. when switching functions)."""
        if self._mode != PIPELINE_MODE:
            self._mode = PIPELINE_MODE
            self.name_label.setText("Pipeline")
            self.name_label.style().unpolish(self.name_label)
            self.name_label.style().polish(self.name_label)

from PyQt5.QtWidgets import QPushButton, QLabel, QHBoxLayout
from PyQt5.QtGui import QIcon
from PyQt5.QtCore import Qt


class AgentModeButton(QPushButton):
    """
    Static indicator button showing 'ReAct' agent mode.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()

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

        self.name_label = QLabel("ReAct")
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

    def current_mode(self) -> str:
        return "react"

    def set_mode(self, mode: str):
        """Kept for API compatibility — always displays 'ReAct'."""
        pass

from PyQt5.QtWidgets import QPushButton, QLabel, QHBoxLayout
from PyQt5.QtGui import QIcon
from PyQt5.QtCore import pyqtSignal, Qt


class WebSearchButton(QPushButton):
    clicked_signal = pyqtSignal(bool)  # 定义点击信号

    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()
        self.websearch_flag = False
        self.clicked.connect(self.set_websearch_enabled)  # 连接内置信号到自定义信号

    def init_ui(self):
        self.setObjectName('switch_websearch_button')
        self.setStyleSheet('''
            QPushButton{
                    width: 102px;
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
        self.icon_label.setFixedSize(16, 16)
        self.icon_label.setPixmap(QIcon("ui/icon/联网搜索.png").pixmap(16, 16))
        self.icon_label.setStyleSheet("""
            QLabel {
                border: none;
                background: transparent;
            }
        """)

        self.name_label = QLabel("联网搜索")
        self.name_label.setStyleSheet("""
            QLabel {
                width: 60px;
                height: 14px;
                font-family: 'Source Han Sans SC';
                font-weight: 400;
                font-size: 14px;
                color: #FFFFFF;
                line-height: 18px;
            }
            QLabel[websearch_flag="true"] {
                color: #409eff;
            }
        """)

        layout = QHBoxLayout()
        layout.setSpacing(3)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.addWidget(self.icon_label, 0, Qt.AlignVCenter)
        layout.addWidget(self.name_label, 0, Qt.AlignVCenter)
        self.setLayout(layout)

    def set_websearch_enabled(self):
        self.websearch_flag = not self.websearch_flag

        self.name_label.setProperty("websearch_flag", self.websearch_flag)
        self.name_label.style().unpolish(self.name_label)
        self.name_label.style().polish(self.name_label)

        self.clicked_signal.emit(self.websearch_flag)


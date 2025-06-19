from PyQt5.QtWidgets import QPushButton, QLabel, QHBoxLayout
from PyQt5.QtGui import QIcon
from PyQt5.QtCore import pyqtSignal, Qt


class NewDialogButton(QPushButton):
    clicked_signal = pyqtSignal()  # 定义点击信号

    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()
        self.clicked.connect(self.emit_click_signal)  # 连接内置信号到自定义信号

    def init_ui(self):
        self.setObjectName('new_dialog_button')
        self.setStyleSheet('''
            QPushButton{
                    width: 102px;
                    height: 36px;
                    background: #30425C;
                    border-radius: 8px;
                    opacity: 0.4;
                }
        ''')

        self.icon_label = QLabel()
        self.icon_label.setFixedSize(16, 16)
        self.icon_label.setPixmap(QIcon("ui/icon/icon_输入框_新建对话.png").pixmap(16, 16))

        self.name_label = QLabel("新建对话")
        self.name_label.setStyleSheet("""
                    width: 56px;
                    height: 14px;
                    font-family: Source Han Sans SC;
                    font-weight: 400;
                    font-size: 14px;
                    color: #FFFFFF;
                    line-height: 18px;
                """)

        layout = QHBoxLayout()
        layout.setSpacing(6)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.addWidget(self.icon_label, 0, Qt.AlignVCenter)
        layout.addWidget(self.name_label, 0, Qt.AlignVCenter)
        self.setLayout(layout)

    def emit_click_signal(self):
        self.clicked_signal.emit()  # 发射自定义信号